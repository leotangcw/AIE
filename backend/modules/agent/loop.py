"""Agent Loop - 核心 Agent 循环处理逻辑"""

import asyncio
import json
import time
from pathlib import Path
from typing import Any, AsyncIterator, Optional

from loguru import logger
from backend.modules.tools.conversation_history import get_conversation_history
from backend.modules.agent.todo_toolkit import TodoToolkit, TodoStatus, format_todo_summary


class AgentLoop:
    """Agent 主循环类 - 处理消息、调用 LLM、执行工具、生成响应"""

    def __init__(
        self,
        provider,
        workspace: Path,
        tools,
        context_builder=None,
        session_manager=None,
        subagent_manager=None,
        model: str | None = None,
        max_iterations: int = 25,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ):
        self.provider = provider
        self.workspace = workspace
        self.tools = tools
        self.context_builder = context_builder
        self.session_manager = session_manager
        self.subagent_manager = subagent_manager
        self.model = model
        self.max_iterations = max_iterations
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.temperature = temperature
        self.max_tokens = max_tokens

        logger.debug(
            f"AgentLoop initialized: workspace={workspace}, "
            f"max_iterations={max_iterations}, max_retries={max_retries}, "
            f"temperature={temperature}, max_tokens={max_tokens}"
        )

    def _resolve_execution_runtime(
        self,
        model_override: Optional[dict[str, Any]] = None,
    ) -> tuple[Any, Optional[str], float, int, int]:
        """解析当前消息执行应使用的 provider 和模型参数。

        支持会话级模型覆盖：当 model_override 指定了不同的 api_key 或 api_base 时，
        会创建一个新的 LiteLLMProvider 实例。

        Args:
            model_override: 可选的模型覆盖参数，来自 SessionRuntimeConfig

        Returns:
            tuple: (provider, model, temperature, max_tokens, max_iterations)
        """
        base_provider = self.provider
        base_model = self.model
        base_temperature = self.temperature
        base_max_tokens = self.max_tokens
        base_max_iterations = self.max_iterations

        if not model_override:
            return (
                base_provider,
                base_model,
                base_temperature,
                base_max_tokens,
                base_max_iterations,
            )

        # 使用覆盖参数
        candidate_provider = base_provider
        candidate_model = model_override.get("model", base_model)
        candidate_temperature = model_override.get("temperature", base_temperature)
        candidate_max_tokens = model_override.get("max_tokens", base_max_tokens)
        candidate_max_iterations = model_override.get(
            "max_iterations", base_max_iterations
        )

        # 检查是否需要创建新的 provider（api_key 或 api_base 不同）
        override_provider = model_override.get("provider")
        override_api_key = model_override.get("api_key") or None
        override_api_base = model_override.get("api_base") or None

        # 当前 provider 的配置
        current_api_key = getattr(base_provider, "api_key", None) or ""
        current_api_base = getattr(base_provider, "api_base", None) or ""

        # 如果 api_key 或 api_base 不同，需要创建新的 provider
        if override_api_key and override_api_key != current_api_key:
            needs_new_provider = True
        elif override_api_base and override_api_base != current_api_base:
            needs_new_provider = True
        else:
            needs_new_provider = False

        if needs_new_provider:
            try:
                from backend.modules.providers.litellm_provider import LiteLLMProvider

                candidate_provider = LiteLLMProvider(
                    api_key=override_api_key,
                    api_base=override_api_base,
                    default_model=candidate_model,
                    timeout=getattr(base_provider, "timeout", 120.0),
                    max_retries=getattr(base_provider, "max_retries", self.max_retries),
                    provider_id=override_provider,
                )
                logger.info(
                    f"Created new LiteLLMProvider for session override: "
                    f"provider={override_provider}, model={candidate_model}"
                )
            except Exception as exc:
                logger.warning(
                    f"Failed to create runtime provider override, falling back to base runtime config: {exc}"
                )
                return (
                    base_provider,
                    base_model,
                    base_temperature,
                    base_max_tokens,
                    base_max_iterations,
                )

        return (
            candidate_provider,
            candidate_model,
            candidate_temperature,
            candidate_max_tokens,
            candidate_max_iterations,
        )

    async def _get_interrupt_supplement(self, session_id: str) -> str:
        """获取中断补充消息，包含当前待办事项上下文

        Args:
            session_id: 会话 ID

        Returns:
            str: 格式化后的中断补充消息
        """
        from backend.modules.agent.todo_toolkit import get_interrupt_supplement as _get_interrupt_supplement
        return await _get_interrupt_supplement(session_id)

    async def process_message(
        self,
        message: str,
        session_id: str,
        context: list[dict[str, Any]] | None = None,
        media: list[str] | None = None,
        channel: str | None = None,
        chat_id: str | None = None,
        cancel_token=None,
        yield_intermediate: bool = True,
        model_override: dict[str, Any] | None = None,
    ) -> AsyncIterator[str]:
        """处理用户消息并生成流式响应

        Args:
            yield_intermediate: 是否输出中间迭代内容
                               True: Web UI 流式模式，实时输出
                               False: 频道模式，仅输出最终回复
            model_override: 可选的会话级模型覆盖参数，来自 SessionRuntimeConfig
        """
        logger.info(f"Processing message for session {session_id}: {message[:50]}...")

        # 解析执行时配置（支持会话级模型覆盖）
        runtime_provider, runtime_model, runtime_temperature, runtime_max_tokens, runtime_max_iterations = (
            self._resolve_execution_runtime(model_override)
        )

        # 设置工具注册表的会话ID（用于审计日志）和渠道信息
        if self.tools:
            self.tools.set_session_id(session_id)
            self.tools.set_channel(channel)

            spawn_tool = self.tools.get_tool("spawn")
            if spawn_tool and hasattr(spawn_tool, "set_context"):
                spawn_tool.set_context(session_id)

        if self.context_builder and context is not None:
            messages = self.context_builder.build_messages(
                history=context,
                current_message=message,
                media=media,
                channel=channel,
                chat_id=chat_id,
            )
        else:
            if context is None:
                context = []

            messages = list(context)
            messages.append({"role": "user", "content": message})

        iteration = 0
        total_tool_calls = 0
        final_content = ""

        try:
            while iteration < runtime_max_iterations:
                iteration += 1

                # 检查是否被取消
                if cancel_token and cancel_token.is_cancelled:
                    logger.info(f"Agent loop cancelled at iteration {iteration}: {session_id}")
                    # 获取中断补充消息
                    supplement = await self._get_interrupt_supplement(session_id)
                    if supplement:
                        yield f"\n\n[任务被中断]{supplement}"
                    return

                logger.debug(
                    f"Agent iteration {iteration}/{runtime_max_iterations}, total tool calls: {total_tool_calls}"
                )

                # 获取基础工具定义
                tool_definitions = self.tools.get_definitions() if self.tools else []

                # 合并 Todo 工具定义 (TodoToolkit 是 session 级别的)
                todo_tool_defs = TodoToolkit.get_tool_definitions()
                tool_definitions = tool_definitions + todo_tool_defs

                content_buffer = ""
                tool_calls_buffer = []
                finish_reason = None
                reasoning_buffer = ""

                async for chunk in runtime_provider.chat_stream(
                    messages=messages,
                    tools=tool_definitions,
                    model=runtime_model,
                    temperature=runtime_temperature,
                    max_tokens=runtime_max_tokens,
                ):
                    if chunk.is_content and chunk.content:
                        content_buffer += chunk.content
                        # Web UI 模式实时输出，频道模式仅缓冲
                        if yield_intermediate:
                            yield chunk.content
                    
                    if chunk.is_tool_call and chunk.tool_call:
                        tool_calls_buffer.append(chunk.tool_call)
                    
                    if chunk.is_reasoning and chunk.reasoning_content:
                        reasoning_buffer += chunk.reasoning_content
                    
                    if chunk.is_done and chunk.finish_reason:
                        finish_reason = chunk.finish_reason
                    
                    if chunk.is_error:
                        # Yield friendly error to user and stop
                        yield chunk.error
                        return
                
                if content_buffer:
                    final_content = content_buffer
                    # 记录AI完整响应
                    logger.info(f"AI完整响应 (长度: {len(content_buffer)}字符):\n{content_buffer}")
                
                if tool_calls_buffer:
                    tool_call_dicts = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments),
                            },
                        }
                        for tc in tool_calls_buffer
                    ]
                    
                    if self.context_builder:
                        messages = self.context_builder.add_assistant_message(
                            messages,
                            content_buffer or None,
                            tool_call_dicts,
                            reasoning_content=reasoning_buffer or None,
                        )
                    else:
                        msg = {
                            "role": "assistant",
                            "content": content_buffer or "",
                            "tool_calls": tool_call_dicts,
                        }
                        if reasoning_buffer:
                            msg["reasoning_content"] = reasoning_buffer
                        messages.append(msg)
                    
                    for tool_call in tool_calls_buffer:
                        if total_tool_calls >= runtime_max_iterations:
                            logger.warning(
                                f"Reached max tool calls limit ({runtime_max_iterations}), "
                                f"skipping remaining tool calls in this iteration"
                            )
                            break

                        # 检查是否被取消
                        if cancel_token and cancel_token.is_cancelled:
                            logger.info(f"Agent loop cancelled before tool execution: {session_id}")
                            # 获取中断补充消息
                            supplement = await self._get_interrupt_supplement(session_id)
                            if supplement:
                                yield f"\n\n[任务被中断]{supplement}"
                            return

                        total_tool_calls += 1
                        tool_name = tool_call.name
                        tool_args = tool_call.arguments
                        tool_id = tool_call.id

                        logger.info(
                            f"Executing tool {total_tool_calls}/{runtime_max_iterations}: "
                            f"{tool_name} with args: {json.dumps(tool_args, ensure_ascii=False)}"
                        )
                        
                        # 发送工具调用开始通知
                        try:
                            from backend.ws.tool_notifications import notify_tool_execution
                            await notify_tool_execution(
                                session_id=session_id,
                                tool_name=tool_name,
                                arguments=tool_args,
                            )
                        except Exception as e:
                            logger.warning(f"Failed to send tool notification: {e}")
                        
                        # 记录工具调用开始时间
                        start_time = time.time()
                        
                        # 尝试执行工具，带重试机制
                        result = None
                        last_error = None
                        
                        for attempt in range(self.max_retries):
                            try:
                                # 执行工具 (检查是否是 todo 工具)
                                if tool_name in TodoToolkit.TOOL_NAMES:
                                    result = await self._execute_todo_tool(tool_name, tool_args, session_id)
                                else:
                                    result = await self.execute_tool(tool_name, tool_args)
                                logger.debug(f"Tool {tool_name} executed successfully")
                                break
                                
                            except Exception as e:
                                last_error = e
                                logger.warning(
                                    f"Tool {tool_name} failed (attempt {attempt + 1}/{self.max_retries}): {e}"
                                )
                                
                                # 如果不是最后一次尝试，等待后重试
                                if attempt < self.max_retries - 1:
                                    await asyncio.sleep(self.retry_delay)
                        
                        # 计算执行耗时
                        duration_ms = int((time.time() - start_time) * 1000)
                        
                        # 添加工具结果到消息列表
                        if result is not None:
                            # 记录工具调用对话（成功）
                            try:
                                conversation_history = get_conversation_history()
                                conversation_history.add_conversation(
                                    session_id=session_id,
                                    tool_name=tool_name,
                                    arguments=tool_args,
                                    user_message=message,  # 添加用户消息
                                    result=result,
                                    duration_ms=duration_ms
                                )
                            except Exception as e:
                                logger.warning(f"Failed to record tool conversation: {e}")
                            
                            # 发送工具执行成功通知
                            try:
                                from backend.ws.tool_notifications import notify_tool_execution
                                await notify_tool_execution(
                                    session_id=session_id,
                                    tool_name=tool_name,
                                    arguments=tool_args,
                                    result=result,
                                )
                            except Exception as e:
                                logger.warning(f"Failed to send tool result notification: {e}")
                            
                            if self.context_builder:
                                messages = self.context_builder.add_tool_result(
                                    messages,
                                    tool_id,
                                    tool_name,
                                    result,
                                )
                            else:
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": tool_id,
                                    "name": tool_name,
                                    "content": result,
                                })
                        else:
                            # 所有重试都失败了
                            error_msg = f"Tool execution failed after {self.max_retries} attempts: {str(last_error)}"
                            logger.error(f"Tool {tool_name} failed permanently: {error_msg}")
                            
                            # 记录工具调用对话（失败）
                            try:
                                conversation_history = get_conversation_history()
                                conversation_history.add_conversation(
                                    session_id=session_id,
                                    tool_name=tool_name,
                                    arguments=tool_args,
                                    user_message=message,  # 添加用户消息
                                    error=error_msg,
                                    duration_ms=duration_ms
                                )
                            except Exception as e:
                                logger.warning(f"Failed to record tool conversation: {e}")
                            
                            # 发送工具执行失败通知
                            try:
                                from backend.ws.tool_notifications import notify_tool_execution
                                await notify_tool_execution(
                                    session_id=session_id,
                                    tool_name=tool_name,
                                    arguments=tool_args,
                                    error=error_msg,
                                )
                            except Exception as e:
                                logger.warning(f"Failed to send tool error notification: {e}")
                            
                            if self.context_builder:
                                messages = self.context_builder.add_tool_result(
                                    messages,
                                    tool_id,
                                    tool_name,
                                    error_msg,
                                )
                            else:
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": tool_id,
                                    "name": tool_name,
                                    "content": error_msg,
                                })
                else:
                    # 没有工具调用，结束循环
                    logger.info("No tool calls, ending agent loop")
                    # 频道模式：最终轮输出完整内容
                    if not yield_intermediate and content_buffer:
                        yield content_buffer
                    break
            
            # 检查是否达到限制
            if iteration >= runtime_max_iterations or total_tool_calls >= runtime_max_iterations:
                if total_tool_calls >= runtime_max_iterations:
                    logger.warning(f"Max tool calls ({runtime_max_iterations}) reached")
                    warning_msg = f"\n\n[达到最大工具调用次数 {runtime_max_iterations}]"
                else:
                    logger.warning(f"Max iterations ({runtime_max_iterations}) reached")
                    warning_msg = f"\n\n[达到最大迭代次数 {runtime_max_iterations}]"
                yield warning_msg
                final_content += warning_msg
            
            # 保存到会话（如果有 session_manager）
            if self.session_manager and final_content:
                try:
                    session = self.session_manager.get_or_create(session_id)
                    session.add_message("user", message)
                    session.add_message("assistant", final_content)
                    self.session_manager.save(session)
                except Exception as e:
                    logger.warning(f"Failed to save session: {e}")
            
            # 记录AI完整响应到审计日志
            if self.tools and final_content:
                try:
                    from backend.modules.tools.file_audit_logger import file_audit_logger
                    file_audit_logger.record_ai_response(
                        session_id=session_id,
                        user_message=message,
                        ai_response=final_content,
                        duration_ms=None  # 暂时不记录耗时
                    )
                except Exception as e:
                    logger.warning(f"Failed to record AI response to audit log: {e}")
                
        except Exception as e:
            logger.exception(f"Error in agent loop: {e}")
            raise

    async def execute_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> str:
        """
        执行工具调用
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数
            
        Returns:
            str: 工具执行结果
            
        Raises:
            ValueError: 工具不存在
            Exception: 工具执行失败
        """
        if not self.tools:
            raise ValueError("ToolRegistry not initialized")
        
        logger.debug(f"Executing tool: {tool_name}")
        
        try:
            result = await self.tools.execute(tool_name, arguments, auto_record=False)
            return result
            
        except Exception as e:
            logger.error(f"Tool execution failed: {tool_name} - {e}")
            raise

    async def _execute_todo_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        session_id: str,
    ) -> str:
        """执行 Todo 工具调用

        Args:
            tool_name: 工具名称
            arguments: 工具参数
            session_id: 会话 ID

        Returns:
            str: 工具执行结果
        """
        from backend.database import AsyncSessionLocal

        logger.debug(f"Executing todo tool: {tool_name}")

        try:
            async with AsyncSessionLocal() as db:
                toolkit = TodoToolkit(session_id=session_id, db=db)

                if tool_name == "todo_create":
                    tasks = arguments.get("tasks", [])
                    result = await toolkit.todo_create(tasks)
                elif tool_name == "todo_complete":
                    idx = arguments.get("idx")
                    result = await toolkit.todo_complete(idx, arguments.get("result", "done"))
                elif tool_name == "todo_insert":
                    idx = arguments.get("idx", 0)
                    tasks = arguments.get("tasks", [])
                    result = await toolkit.todo_insert(idx, tasks)
                elif tool_name == "todo_remove":
                    idx = arguments.get("idx")
                    result = await toolkit.todo_remove(idx)
                elif tool_name == "todo_clear":
                    result = await toolkit.todo_clear()
                elif tool_name == "todo_list":
                    result = await toolkit.todo_list()
                else:
                    result = f"错误：未知的 todo 工具 {tool_name}"

                return result

        except Exception as e:
            logger.error(f"Todo tool execution failed: {tool_name} - {e}")
            raise

    async def process_direct(
        self,
        content: str,
        session_id: str = "cli:direct",
        channel: str = "cli",
        chat_id: str = "direct",
    ) -> str:
        """
        直接处理消息（用于 CLI 或 cron 使用）
        
        Args:
            content: 消息内容
            session_id: 会话标识符
            channel: 来源渠道（用于上下文）
            chat_id: 来源聊天 ID（用于上下文）
        
        Returns:
            Agent 的响应
        """
        response_parts = []
        
        async for chunk in self.process_message(
            message=content,
            session_id=session_id,
            channel=channel,
            chat_id=chat_id,
        ):
            response_parts.append(chunk)
        
        return "".join(response_parts)
