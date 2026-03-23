"""Memory Plugin - MCP Server 生命周期管理.

自动管理 Memory-MCP-Server 的启动/停止，作为 AIE 的内置 MCP 组件。
支持可拔插：可以配置不同的 MCP Server URL。
"""

import asyncio
import subprocess
from pathlib import Path
from typing import Optional

from loguru import logger

from backend.utils.paths import WORKSPACE_DIR


class MemoryPlugin:
    """
    Memory MCP Plugin - 自动管理 MCP Server 生命周期.

    功能：
    - AIE 启动时自动启动 MCP Server
    - AIE 关闭时自动停止 MCP Server
    - 提供 MCP Client 供 Agent 调用
    - 支持配置不同的 MCP Server
    """

    def __init__(
        self,
        mcp_server_path: str | Path | None = None,
        config_path: str | Path | None = None,
        db_path: str | Path | None = None,
        auto_start: bool = True,
    ):
        """
        初始化 Memory Plugin.

        Args:
            mcp_server_path: Memory-MCP-Server 代码路径
            config_path: 配置文件路径
            db_path: 数据库路径（默认使用 AIE memory 目录）
            auto_start: 是否在 start() 时自动启动 MCP Server
        """
        # 默认路径
        if mcp_server_path is None:
            mcp_server_path = Path(__file__).parent.parent.parent.parent.parent / "refcode" / "Memory-MCP-Server"

        self.mcp_server_path = Path(mcp_server_path)
        self.config_path = Path(config_path) if config_path else self.mcp_server_path / "config" / "default.yaml"

        # 默认使用 AIE 的 memory 目录
        if db_path is None:
            db_path = WORKSPACE_DIR / "memory" / "vector_memory.db"

        self.db_path = Path(db_path)
        self.auto_start = auto_start

        self.process: Optional[subprocess.Popen] = None
        self._client: Optional["MCPClient"] = None
        self._started = False
        self._installed = False

    async def _ensure_package_installed(self) -> bool:
        """确保 Memory-MCP-Server 作为 editable 包已安装."""
        if self._installed:
            return True

        try:
            import sys
            # 检查是否已安装
            result = subprocess.run(
                [sys.executable, "-c", "import memory_mcp_server"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                logger.info("Memory-MCP-Server package already installed")
                self._installed = True
                return True

            # 安装为 editable 包
            logger.info(f"Installing Memory-MCP-Server from {self.mcp_server_path}")
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-e", str(self.mcp_server_path)],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                logger.info("Memory-MCP-Server installed successfully")
                self._installed = True
                return True
            else:
                logger.error(f"Failed to install Memory-MCP-Server: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"Error installing Memory-MCP-Server: {e}")
            return False

    async def start(self) -> bool:
        """
        启动 Memory MCP Server.

        Returns:
            是否启动成功
        """
        if self._started:
            logger.info("MemoryPlugin already started")
            return True

        # 检查 server 路径是否存在
        if not self.mcp_server_path.exists():
            logger.warning(f"Memory-MCP-Server not found at {self.mcp_server_path}")
            logger.info("MemoryPlugin will be disabled")
            return False

        # 创建 db 目录
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # 先安装 Memory-MCP-Server 作为 editable 包（如果尚未安装）
        await self._ensure_package_installed()

        # 构建启动命令
        cmd = [
            "python3", "-m", "memory_mcp_server.main",
            f"--config={self.config_path}",
        ]

        logger.info(f"Starting Memory-MCP-Server: {' '.join(cmd)}")

        try:
            import os
            env = os.environ.copy()
            # 确保使用正确的 db_path（通过环境变量或配置）
            env["MEMORY_DB_PATH"] = str(self.db_path)

            self.process = subprocess.Popen(
                cmd,
                cwd=str(self.mcp_server_path),
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            # 等待进程启动
            await asyncio.sleep(2)

            # 检查进程是否还在运行
            if self.process.poll() is not None:
                # 进程已退出
                stdout, stderr = self.process.communicate()
                logger.error(f"Memory-MCP-Server exited with code {self.process.returncode}")
                logger.error(f"stdout: {stdout.decode()[:500]}")
                logger.error(f"stderr: {stderr.decode()[:500]}")
                return False

            # 初始化 MCP Client (5分钟超时，用于首次模型加载)
            from .client import MCPClient
            self._client = MCPClient(server_command=cmd, timeout=300.0)
            await self._client.start()  # 启动 subprocess
            await self._client.initialize()

            self._started = True
            logger.info("Memory-MCP-Server started successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to start Memory-MCP-Server: {e}")
            self.process = None
            return False

    async def stop(self) -> None:
        """停止 Memory MCP Server."""
        if not self._started:
            return

        logger.info("Stopping Memory-MCP-Server...")

        if self._client:
            try:
                await self._client.stop()
            except Exception as e:
                logger.warning(f"Error stopping MCP client: {e}")
            self._client = None

        if self.process:
            try:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()
            except Exception as e:
                logger.warning(f"Error stopping process: {e}")
            self.process = None

        self._started = False
        logger.info("Memory-MCP-Server stopped")

    async def restart(self) -> bool:
        """重启 MCP Server."""
        await self.stop()
        await asyncio.sleep(1)
        return await self.start()

    @property
    def is_running(self) -> bool:
        """检查 MCP Server 是否在运行."""
        if not self._started or self.process is None:
            return False
        return self.process.poll() is None

    @property
    def client(self) -> Optional["MCPClient"]:
        """获取 MCP Client."""
        return self._client

    def get_mcp_client(self) -> Optional["MCPClient"]:
        """获取 MCP Client（兼容性别名）."""
        return self._client


# 全局实例
_memory_plugin: Optional[MemoryPlugin] = None


def get_memory_plugin() -> Optional[MemoryPlugin]:
    """获取全局 MemoryPlugin 实例."""
    return _memory_plugin


async def init_memory_plugin(
    mcp_server_path: str | Path | None = None,
    config_path: str | Path | None = None,
    db_path: str | Path | None = None,
    auto_start: bool = True,
) -> Optional[MemoryPlugin]:
    """
    初始化 Memory Plugin.

    Args:
        mcp_server_path: Memory-MCP-Server 代码路径
        config_path: 配置文件路径
        db_path: 数据库路径
        auto_start: 是否自动启动

    Returns:
        MemoryPlugin 实例或 None
    """
    global _memory_plugin

    if _memory_plugin is not None:
        return _memory_plugin

    _memory_plugin = MemoryPlugin(
        mcp_server_path=mcp_server_path,
        config_path=config_path,
        db_path=db_path,
        auto_start=auto_start,
    )

    if auto_start:
        await _memory_plugin.start()

    return _memory_plugin


async def close_memory_plugin() -> None:
    """关闭 Memory Plugin."""
    global _memory_plugin

    if _memory_plugin:
        await _memory_plugin.stop()
        _memory_plugin = None
