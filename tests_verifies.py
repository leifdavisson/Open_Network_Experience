def verifies(*req_ids):
    def decorator(func):
        # Attach req_ids to the function if needed for runtime, but AST parser doesn't need runtime execution.
        func.__verifies__ = req_ids
        return func
    return decorator
