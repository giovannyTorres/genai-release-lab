"""Strict JSON boundary shared by API and offline CLI."""

import json
import math


def strict_loads(content):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON object keys")
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError("Non-finite JSON numbers are not permitted")

    def finite_float(value):
        result = float(value)
        if not math.isfinite(result):
            raise ValueError("Non-finite JSON numbers are not permitted")
        return result

    return json.loads(
        content, object_pairs_hook=pairs, parse_constant=invalid_constant, parse_float=finite_float
    )
