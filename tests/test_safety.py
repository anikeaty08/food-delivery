from food_order_bot.mcp.tools import ToolGroup, classify_tool, may_retry


def test_checkout_tools_are_not_retryable() -> None:
    assert classify_tool("place_food_order") == ToolGroup.CHECKOUT_PAYMENT
    assert classify_tool("checkout") == ToolGroup.CHECKOUT_PAYMENT
    assert not may_retry("place_food_order")
    assert not may_retry("checkout")


def test_read_only_tools_are_retryable() -> None:
    assert classify_tool("search_restaurants") == ToolGroup.READ_ONLY
    assert classify_tool("get_restaurant_menu") == ToolGroup.READ_ONLY
    assert may_retry("search_restaurants")


def test_unknown_mutation_like_names_are_not_read_only() -> None:
    assert classify_tool("submit_payment_intent") == ToolGroup.CHECKOUT_PAYMENT
    assert classify_tool("update_delivery_cart") == ToolGroup.CART_MUTATION
