"""图操作自定义异常类


所有图数据库相关的异常都应该继承自 GraphError 基类。
"""


class GraphError(Exception):
    """图操作基础异常

    所有图数据库相关异常的基类。
    """

    def __init__(self, message: str, original_error: Exception | None = None):
        """
        初始化图错误

        Args:
            message: 错误消息
            original_error: 原始异常（如果有）
        """
        self.message = message
        self.original_error = original_error
        super().__init__(self.message)

    def __str__(self) -> str:
        if self.original_error:
            return f"{self.message}: {self.original_error}"
        return self.message


class GraphConnectionError(GraphError):
    """图数据库连接错误

    当无法连接到图数据库时抛出。
    """

    def __init__(
        self,
        message: str = "Failed to connect to graph database",
        host: str | None = None,
        port: int | None = None,
        original_error: Exception | None = None
    ):
        self.host = host
        self.port = port
        if host and port:
            message = f"{message} at {host}:{port}"
        super().__init__(message, original_error)


class GraphQueryError(GraphError):
    """图查询错误

    当查询语法错误、执行失败或结果处理出错时抛出。
    """

    def __init__(
        self,
        message: str,
        query: str | None = None,
        parameters: dict | None = None,
        original_error: Exception | None = None
    ):
        self.query = query
        self.parameters = parameters
        super().__init__(message, original_error)

    def __str__(self) -> str:
        result = super().__str__()
        if self.query:
            result += f"\nQuery: {self.query}"
        if self.parameters:
            result += f"\nParameters: {self.parameters}"
        return result


class GraphDatabaseError(GraphError):
    """图数据库内部错误

    当数据库返回内部错误（如约束违反、超时等）时抛出。
    """

    def __init__(
        self,
        message: str,
        error_code: str | None = None,
        original_error: Exception | None = None
    ):
        self.error_code = error_code
        if error_code:
            message = f"[{error_code}] {message}"
        super().__init__(message, original_error)


class GraphTransactionError(GraphError):
    """图事务错误

    当事务执行失败或需要回滚时抛出。
    """

    def __init__(
        self,
        message: str = "Transaction failed",
        original_error: Exception | None = None
    ):
        super().__init__(message, original_error)


class GraphConstraintError(GraphDatabaseError):
    """图约束错误

    当操作违反数据库约束（如唯一性约束）时抛出。
    """

    def __init__(
        self,
        message: str = "Constraint violation",
        constraint_name: str | None = None,
        original_error: Exception | None = None
    ):
        self.constraint_name = constraint_name
        if constraint_name:
            message = f"{message}: {constraint_name}"
        super().__init__(message, None, original_error)


class GraphTimeoutError(GraphError):
    """图操作超时错误

    当查询执行超过预定时间时抛出。
    """

    def __init__(
        self,
        message: str = "Query execution timed out",
        timeout_seconds: int | None = None,
        original_error: Exception | None = None
    ):
        self.timeout_seconds = timeout_seconds
        if timeout_seconds:
            message = f"{message} after {timeout_seconds} seconds"
        super().__init__(message, original_error)


class GraphValidationError(GraphError):
    """图数据验证错误

    当输入数据不符合预期格式或约束时抛出。
    """

    def __init__(
        self,
        message: str,
        field: str | None = None,
        value: any = None,
        original_error: Exception | None = None
    ):
        self.field = field
        self.value = value
        if field and value is not None:
            message = f"{message}: {field}={value}"
        super().__init__(message, original_error)
