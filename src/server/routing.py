"""Register every analysis tool with a schema-visible, request-local selector."""

import functools
import inspect

from src.server import authorization, instances
from src.server.config import error_response


def instance_tool(mcp):
    def register(function):
        original = inspect.signature(function)
        signature = original.replace(parameters=[*original.parameters.values(),
            inspect.Parameter('instance', inspect.Parameter.KEYWORD_ONLY, default=None, annotation=str | None)])

        @functools.wraps(function)
        async def routed(*args, **kwargs):
            bound = signature.bind(*args, **kwargs)
            bound.apply_defaults()
            selector = bound.arguments.pop('instance')
            identity, error = instances.resolve(selector)
            if error:
                return error_response(error, 'invalid_instance')
            denied = authorization.forbidden(identity)
            if denied:
                return denied
            token = instances.selected_instance.set(identity)
            try:
                return await function(**bound.arguments)
            finally:
                instances.selected_instance.reset(token)

        routed.__signature__ = signature
        routed.__annotations__ = {name: value.annotation for name, value in signature.parameters.items()}
        routed.__annotations__['return'] = signature.return_annotation
        return mcp.tool()(routed)
    return register
