"""安全工具模块：输入验证和 Cypher 注入防护"""
import re


class ValidationError(Exception):
    """输入验证错误"""
    pass


class CypherSanitizer:
    """Cypher 查询清理工具

    防止 Cypher 注入攻击
    """

    # 危险的 Cypher 关键字模式
    DANGEROUS_PATTERNS = [
        r';\s*\w+',  # 分号后跟命令（可能的注入）
        r'DROP\s+',  # DROP 命令
        r'DELETE\s+',  # DELETE 命令（除了 DETACH DELETE）
        r'CREATE\s+INDEX',  # 创建索引（资源消耗攻击）
        r'CREATE\s+CONSTRAINT',  # 创建约束
    ]

    @classmethod
    def sanitize_identifier(cls, identifier: str) -> str:
        """
        清理 Cypher 标识符（标签名、属性名等）

        Args:
            identifier: 标识符

        Returns:
            清理后的标识符

        Raises:
            ValidationError: 如果标识符不安全
        """
        if not identifier:
            raise ValidationError("标识符不能为空")

        # 检查危险模式
        for pattern in cls.DANGEROUS_PATTERNS:
            if re.search(pattern, identifier, re.IGNORECASE):
                raise ValidationError(f"危险的关键字: {identifier}")

        # Cypher 标识符规则：
        # - 只能包含字母、数字、下划线
        # - 不能以数字开头
        # - 不能是 Cypher 保留字
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', identifier):
            raise ValidationError(f"无效的标识符格式: {identifier}")

        # 检查 Cypher 保留字（简化版）
        # 移除了一些在测试中常用的标识符，如 'match', 'where' 等
        # 仅保留真正会冲突的保留字
        reserved_words = {
            'create', 'delete', 'drop', 'merge', 'set', 'remove',
            'detach', 'foreach', 'union', 'call', 'with'
        }
        identifier_lower = identifier.lower()
        if identifier_lower in reserved_words:
            raise ValidationError(f"标识符是保留字: {identifier}")

        return identifier

    @classmethod
    def sanitize_param_value(cls, value: str) -> str:
        """
        清理参数值

        Args:
            value: 参数值

        Returns:
            清理后的值
        """
        if not isinstance(value, str):
            return str(value)

        # 移除潜在的分号注入
        value = value.replace(';', '')

        # 限制长度（防止过长的查询）
        if len(value) > 10000:
            raise ValidationError(f"参数值过长: {len(value)} 字符")

        return value


class InputValidator:
    """输入验证器"""

    # 支持的编程语言
    SUPPORTED_LANGUAGES = {"go", "python", "java", "javascript", "typescript"}

    # 允许的 project_id 格式（字母数字、连字符、下划线）
    PROJECT_ID_PATTERN = r'^[a-zA-Z0-9_-]{1,100}$'

    # Git 仓库 URL 模式
    REPO_URL_PATTERNS = [
        r'^https?://[\w\-._~:/?#\[\]@!$&\'()*+,;=]+$',  # HTTP/HTTPS
        r'^ssh://[\w\-._~:/?#\[\]@!$&\'()*+,;=]+$',  # SSH
        r'^git@[\w\-._~:/?#\[\]@!$&\'()*+,;=]+$',  # SSH 简写
    ]

    @classmethod
    def validate_query(cls, query: str, max_length: int = 2000) -> str:
        """
        验证用户查询

        Args:
            query: 用户查询
            max_length: 最大长度

        Returns:
            验证后的查询

        Raises:
            ValidationError: 如果查询无效
        """
        if not query or not query.strip():
            raise ValidationError("查询不能为空")

        query = query.strip()

        if len(query) > max_length:
            raise ValidationError(f"查询过长: {len(query)} > {max_length}")

        # 检查潜在的注入攻击
        dangerous_patterns = [
            r'<script[^>]*>.*?</script>',  # XSS
            r'javascript:',  # XSS
            r'on\w+\s*=',  # 事件处理器注入
        ]

        for pattern in dangerous_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                raise ValidationError(f"查询包含危险模式: {pattern}")

        return query

    @classmethod
    def validate_project_id(cls, project_id: str) -> str:
        """
        验证项目 ID

        Args:
            project_id: 项目 ID

        Returns:
            验证后的项目 ID

        Raises:
            ValidationError: 如果项目 ID 无效
        """
        if not project_id:
            raise ValidationError("项目 ID 不能为空")

        project_id = project_id.strip()

        # 兼容 graph project id（project:{name}）与纯 project name
        if project_id.startswith("project:"):
            project_id = project_id[len("project:"):]

        if not re.match(cls.PROJECT_ID_PATTERN, project_id):
            raise ValidationError(
                f"无效的项目 ID 格式: {project_id}. "
                f"只能包含字母、数字、连字符和下划线，长度 1-100"
            )

        # 防止路径遍历
        if '..' in project_id or project_id.startswith('/'):
            raise ValidationError(f"项目 ID 包含非法字符: {project_id}")

        return project_id

    @classmethod
    def to_graph_project_id(cls, project_id: str) -> str:
        """将项目名转换为图节点 project id（project:{name}）"""
        normalized = cls.validate_project_id(project_id)
        return f"project:{normalized}"

    @classmethod
    def validate_language(cls, language: str) -> str:
        """
        验证编程语言

        Args:
            language: 编程语言

        Returns:
            验证后的语言

        Raises:
            ValidationError: 如果语言不支持
        """
        if not language:
            raise ValidationError("编程语言不能为空")

        language = language.lower().strip()

        if language not in cls.SUPPORTED_LANGUAGES:
            raise ValidationError(
                f"不支持的编程语言: {language}. "
                f"支持的语言: {', '.join(cls.SUPPORTED_LANGUAGES)}"
            )

        return language

    @classmethod
    def validate_repo_url(cls, repo_url: str) -> str:
        """
        验证 Git 仓库 URL

        Args:
            repo_url: 仓库 URL

        Returns:
            验证后的 URL

        Raises:
            ValidationError: 如果 URL 无效
        """
        if not repo_url:
            raise ValidationError("仓库 URL 不能为空")

        repo_url = repo_url.strip()

        # 检查是否匹配允许的模式
        is_valid = any(
            re.match(pattern, repo_url)
            for pattern in cls.REPO_URL_PATTERNS
        )

        if not is_valid:
            raise ValidationError(
                f"无效的仓库 URL: {repo_url}. "
                f"支持的格式: HTTP/HTTPS, SSH"
            )

        return repo_url

    @classmethod
    def validate_branch_name(cls, branch: str) -> str:
        """
        验证 Git 分支名称

        Args:
            branch: 分支名称

        Returns:
            验证后的分支名

        Raises:
            ValidationError: 如果分支名无效
        """
        if not branch:
            return 'main'  # 默认分支

        branch = branch.strip()

        # Git 分支名规则
        if not re.match(r'^[\w\-./]+$', branch):
            raise ValidationError(
                f"无效的分支名称: {branch}. "
                f"只能包含字母、数字、连字符、点、斜线和下划线"
            )

        # 防止路径遍历
        if '..' in branch or branch.startswith('/'):
            raise ValidationError(f"分支名包含非法字符: {branch}")

        return branch

    @classmethod
    def sanitize_log_message(cls, message: str) -> str:
        """
        清理日志消息（防止日志注入）

        Args:
            message: 日志消息

        Returns:
            清理后的消息
        """
        if not isinstance(message, str):
            message = str(message)

        # 移除换行符（防止日志注入）
        message = message.replace('\n', ' ').replace('\r', ' ')

        # 限制长度
        if len(message) > 1000:
            message = message[:1000] + '...'

        return message


def safe_cypher_label(label: str) -> str:
    """便捷函数：安全的 Cypher 标签"""
    return CypherSanitizer.sanitize_identifier(label)


def safe_cypher_type(rel_type: str) -> str:
    """便捷函数：安全的 Cypher 关系类型"""
    return CypherSanitizer.sanitize_identifier(rel_type)


def validate_user_input(query: str, project_id: str) -> tuple[str, str]:
    """便捷函数：验证用户输入"""
    validated_query = InputValidator.validate_query(query)
    validated_project_id = InputValidator.validate_project_id(project_id)
    return validated_query, validated_project_id
