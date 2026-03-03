"""AIE 企业规则系统 - 规则加载、评估和应用"""

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from loguru import logger

from backend.utils.paths import MEMORY_DIR


class Rule:
    """规则数据类"""

    def __init__(
        self,
        name: str,
        description: str,
        content: str,
        file_path: Path = None,
        enabled: bool = True,
        priority: int = 0,
        rule_type: str = "general",  # general, approval, workflow, security
    ):
        self.id = str(uuid.uuid4())
        self.name = name
        self.description = description
        self.content = content
        self.file_path = file_path
        self.enabled = enabled
        self.priority = priority
        self.rule_type = rule_type
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "content": self.content,
            "enabled": self.enabled,
            "priority": self.priority,
            "rule_type": self.rule_type,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Rule":
        rule = cls(
            name=data["name"],
            description=data["description"],
            content=data["content"],
            enabled=data.get("enabled", True),
            priority=data.get("priority", 0),
            rule_type=data.get("rule_type", "general"),
        )
        rule.id = data.get("id", rule.id)
        rule.created_at = data.get("created_at", rule.created_at)
        rule.updated_at = data.get("updated_at", rule.updated_at)
        return rule


class RuleResult:
    """规则评估结果"""

    def __init__(
        self,
        rule_id: str,
        rule_name: str,
        passed: bool,
        message: str = "",
        action: str = "allow",  # allow, deny, warn, require_approval
        data: dict = None,
    ):
        self.rule_id = rule_id
        self.rule_name = rule_name
        self.passed = passed
        self.message = message
        self.action = action
        self.data = data or {}

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "passed": self.passed,
            "message": self.message,
            "action": self.action,
            "data": self.data,
        }


class RulesEngine:
    """规则引擎"""

    def __init__(self, rules_dir: Path = None):
        self.rules_dir = rules_dir or MEMORY_DIR / "rules"
        self.rules_dir.mkdir(parents=True, exist_ok=True)

        self._rules: dict[str, Rule] = {}
        self._load_rules()

    def _load_rules(self):
        """从目录加载规则"""
        # 加载 JSON 格式规则
        for file in self.rules_dir.glob("*.json"):
            try:
                data = json.loads(file.read_text(encoding="utf-8"))
                rule = Rule.from_dict(data)
                self._rules[rule.id] = rule
            except Exception as e:
                logger.warning(f"Failed to load rule from {file}: {e}")

        # 加载 Markdown 格式规则
        for file in self.rules_dir.glob("*.md"):
            try:
                content = file.read_text(encoding="utf-8")
                rule = self._parse_markdown_rule(file.stem, content, file)
                if rule:
                    self._rules[rule.id] = rule
            except Exception as e:
                logger.warning(f"Failed to load rule from {file}: {e}")

        logger.info(f"Loaded {len(self._rules)} rules")

    def _parse_markdown_rule(self, name: str, content: str, file_path: Path) -> Optional[Rule]:
        """解析 Markdown 格式规则"""
        # 简单解析: 第一个 # 标题作为名称, 后面是内容
        lines = content.split("\n")
        description = ""
        for line in lines:
            if line.startswith("# ") and not line.startswith("##"):
                continue
            if line.strip() and not line.startswith("#"):
                description = line.strip()[:200]
                break

        return Rule(
            name=name,
            description=description,
            content=content,
            file_path=file_path,
            enabled=True,
            rule_type="general",
        )

    def add_rule(self, rule: Rule):
        """添加规则"""
        self._rules[rule.id] = rule
        # 保存到文件
        rule_file = self.rules_dir / f"{rule.id}.json"
        rule_file.write_text(
            json.dumps(rule.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        logger.info(f"Added rule: {rule.name}")

    def update_rule(self, rule_id: str, **kwargs):
        """更新规则"""
        rule = self._rules.get(rule_id)
        if not rule:
            return False

        for key, value in kwargs.items():
            if hasattr(rule, key):
                setattr(rule, key, value)

        rule.updated_at = datetime.now().isoformat()

        # 保存
        rule_file = self.rules_dir / f"{rule_id}.json"
        rule_file.write_text(
            json.dumps(rule.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        return True

    def delete_rule(self, rule_id: str):
        """删除规则"""
        if rule_id in self._rules:
            rule = self._rules.pop(rule_id)
            # 删除文件
            rule_file = self.rules_dir / f"{rule_id}.json"
            if rule_file.exists():
                rule_file.unlink()
            logger.info(f"Deleted rule: {rule.name}")
            return True
        return False

    def get_rule(self, rule_id: str) -> Optional[Rule]:
        """获取规则"""
        return self._rules.get(rule_id)

    def get_all_rules(self) -> list[Rule]:
        """获取所有规则"""
        return sorted(self._rules.values(), key=lambda r: r.priority, reverse=True)

    def get_enabled_rules(self) -> list[Rule]:
        """获取启用的规则"""
        return sorted(
            [r for r in self._rules.values() if r.enabled],
            key=lambda r: r.priority,
            reverse=True
        )

    def evaluate(self, context: dict[str, Any]) -> list[RuleResult]:
        """评估规则"""
        results = []
        enabled_rules = self.get_enabled_rules()

        for rule in enabled_rules:
            result = self._evaluate_rule(rule, context)
            results.append(result)

            # 如果是否决规则且不通过，停止评估
            if result.action == "deny" and not result.passed:
                break

        return results

    def _evaluate_rule(self, rule: Rule, context: dict[str, Any]) -> RuleResult:
        """评估单条规则 - 简化实现"""
        # 简化: 基于关键词匹配
        # 生产环境应该使用更复杂的规则引擎

        content = rule.content.lower()
        user_input = context.get("user_input", "").lower()
        action = context.get("action", "").lower()

        passed = True
        message = ""

        # 检查是否包含某些关键词需要审批
        if "需要审批" in content or "approval" in content.lower():
            approval_keywords = ["请假", "报销", "采购", "合同", "预算"]
            if any(kw in user_input for kw in approval_keywords):
                passed = False
                message = f"操作 '{action}' 需要审批"
                return RuleResult(
                    rule_id=rule.id,
                    rule_name=rule.name,
                    passed=passed,
                    message=message,
                    action="require_approval",
                )

        return RuleResult(
            rule_id=rule.id,
            rule_name=rule.name,
            passed=passed,
            message=message,
            action="allow",
        )

    def import_from_document(self, file_path: Path) -> Rule:
        """从文档导入规则"""
        content = file_path.read_text(encoding="utf-8")

        # 提取名称
        name = file_path.stem
        for line in content.split("\n"):
            if line.startswith("# "):
                name = line[2:].strip()
                break

        rule = Rule(
            name=name,
            description=f"从 {file_path.name} 导入",
            content=content,
            file_path=file_path,
            enabled=True,
            rule_type="general",
        )

        self.add_rule(rule)
        return rule


class AieTemplate:
    """AIE 初始化模板"""

    def __init__(
        self,
        name: str,
        description: str,
        rules: list[str] = None,  # 规则 ID 列表
        skills: list[str] = None,  # 技能 ID 列表
        default_config: dict = None,
    ):
        self.id = str(uuid.uuid4())
        self.name = name
        self.description = description
        self.rules = rules or []
        self.skills = skills or []
        self.default_config = default_config or {}
        self.created_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "rules": self.rules,
            "skills": self.skills,
            "default_config": self.default_config,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AieTemplate":
        template = cls(
            name=data["name"],
            description=data["description"],
            rules=data.get("rules", []),
            skills=data.get("skills", []),
            default_config=data.get("default_config", {}),
        )
        template.id = data.get("id", template.id)
        template.created_at = data.get("created_at", template.created_at)
        return template


class TemplateManager:
    """模板管理器"""

    def __init__(self, templates_dir: Path = None):
        self.templates_dir = templates_dir or MEMORY_DIR / "templates"
        self.templates_dir.mkdir(parents=True, exist_ok=True)

        self._templates: dict[str, AieTemplate] = {}
        self._load_templates()

    def _load_templates(self):
        """加载模板"""
        for file in self.templates_dir.glob("*.json"):
            try:
                data = json.loads(file.read_text(encoding="utf-8"))
                template = AieTemplate.from_dict(data)
                self._templates[template.id] = template
            except Exception as e:
                logger.warning(f"Failed to load template from {file}: {e}")
        logger.info(f"Loaded {len(self._templates)} templates")

    def add_template(self, template: AieTemplate):
        """添加模板"""
        self._templates[template.id] = template
        template_file = self.templates_dir / f"{template.id}.json"
        template_file.write_text(
            json.dumps(template.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        logger.info(f"Added template: {template.name}")

    def get_template(self, template_id: str) -> Optional[AieTemplate]:
        return self._templates.get(template_id)

    def get_all_templates(self) -> list[AieTemplate]:
        return list(self._templates.values())

    def delete_template(self, template_id: str):
        if template_id in self._templates:
            template = self._templates.pop(template_id)
            template_file = self.templates_dir / f"{template_id}.json"
            if template_file.exists():
                template_file.unlink()
            return True
        return False


# 全局实例
_rules_engine: Optional[RulesEngine] = None
_template_manager: Optional[TemplateManager] = None


def get_rules_engine() -> RulesEngine:
    global _rules_engine
    if _rules_engine is None:
        _rules_engine = RulesEngine()
    return _rules_engine


def get_template_manager() -> TemplateManager:
    global _template_manager
    if _template_manager is None:
        _template_manager = TemplateManager()
    return _template_manager
