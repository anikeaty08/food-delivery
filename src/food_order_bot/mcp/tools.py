from enum import StrEnum


class ToolGroup(StrEnum):
    READ_ONLY = "read_only"
    CART_MUTATION = "cart_mutation"
    CHECKOUT_PAYMENT = "checkout_payment"
    BOOKING = "booking"


CHECKOUT_PAYMENT_TOOLS = {
    "place_food_order",
    "checkout",
}

BOOKING_TOOLS = {
    "book_table",
}

CART_MUTATION_TOOLS = {
    "update_food_cart",
    "flush_food_cart",
    "update_cart",
    "clear_cart",
    "create_cart",
    "apply_food_coupon",
    "create_address",
    "delete_address",
}


def classify_tool(tool_name: str) -> ToolGroup:
    if tool_name in CHECKOUT_PAYMENT_TOOLS:
        return ToolGroup.CHECKOUT_PAYMENT
    if tool_name in BOOKING_TOOLS:
        return ToolGroup.BOOKING
    if tool_name in CART_MUTATION_TOOLS:
        return ToolGroup.CART_MUTATION
    lowered = tool_name.lower()
    read_prefixes = ("get_", "fetch_", "track_", "list_", "status", "details")
    if any(token in lowered for token in ("checkout", "payment", "order", "place")):
        if any(token in lowered for token in read_prefixes):
            return ToolGroup.READ_ONLY
        return ToolGroup.CHECKOUT_PAYMENT
    if any(token in lowered for token in ("book", "booking", "reserve")):
        if any(token in lowered for token in read_prefixes):
            return ToolGroup.READ_ONLY
        return ToolGroup.BOOKING
    if any(token in lowered for token in ("update", "clear", "flush", "delete", "create", "apply")):
        return ToolGroup.CART_MUTATION
    return ToolGroup.READ_ONLY


def may_retry(tool_name: str) -> bool:
    return classify_tool(tool_name) == ToolGroup.READ_ONLY
