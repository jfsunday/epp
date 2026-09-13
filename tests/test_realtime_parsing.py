"""Parser and AST tests for the real-time, canvas and widget statements.

These run headless: they only check that the source turns into the right
nodes, never that a window appears.
"""

from epp import ast_nodes as ast
from epp.lexer import lex
from epp.parser import parse


def first(source: str):
    return parse(lex(source))[0]


class TestTicks:
    def test_every_milliseconds(self):
        node = first("Every 50 milliseconds, do the following.\nSay hi.\nEnd every.")
        assert isinstance(node, ast.EveryStmt)
        assert node.interval.value == 50
        assert len(node.body) == 1

    def test_every_seconds_becomes_milliseconds(self):
        node = first("Every 2 seconds, do the following.\nSay hi.\nEnd every.")
        assert node.interval.op == "times"
        assert node.interval.right.value == 1000

    def test_stop_ticking(self):
        assert isinstance(first("Stop ticking."), ast.StopTickingStmt)


class TestKeyboardAndMouse:
    def test_when_key(self):
        node = first("When key space is pressed, do the following.\nSay jump.\nEnd when.")
        assert isinstance(node, ast.WhenKeyStmt)
        assert node.key == "space"

    def test_when_key_with_two_words(self):
        node = first("When key arrow left is pressed, do the following.\nSay go.\nEnd when.")
        assert node.key == "arrow left"

    def test_when_mouse_clicked(self):
        node = first("When the mouse is clicked, do the following.\nSay hit.\nEnd when.")
        assert isinstance(node, ast.WhenMouseStmt)
        assert node.event == "clicked"

    def test_key_pressed_expression(self):
        node = first("Let jumping be key spacebar is pressed.")
        assert isinstance(node.value, ast.KeyPressedExpr)
        assert node.value.key == "spacebar"

    def test_mouse_coordinates(self):
        node = first("Let across be the mouse x.")
        assert isinstance(node.value, ast.MouseCoordExpr)
        assert node.value.axis == "x"


class TestSprites:
    def test_add_sprite_with_image(self):
        node = first("Add sprite bird with image bird.png.")
        assert isinstance(node, ast.AddSpriteStmt)
        assert node.image.value == "bird.png"

    def test_add_sprite_without_image(self):
        assert first("Add sprite bird.").image is None

    def test_image_path_uses_slash(self):
        node = first("Add sprite bird with image examples slash images slash bird.png.")
        assert node.image.value == "examples/images/bird.png"

    def test_set_position(self):
        node = first("Set position of bird to 100 by 200.")
        assert isinstance(node, ast.SetSpritePositionStmt)
        assert (node.x.value, node.y.value) == (100, 200)

    def test_move_sprite(self):
        node = first("Move sprite bird by 0 by 5.")
        assert isinstance(node, ast.MoveSpriteStmt)
        assert node.dy.value == 5

    def test_sprite_coordinate(self):
        node = first("Let height be the y of bird.")
        assert isinstance(node.value, ast.SpriteCoordExpr)
        assert (node.value.name, node.value.axis) == ("bird", "y")

    def test_sprite_coordinate_can_be_compared(self):
        node = first("If the x of bird is greater than 470, do the following.\nSay out.\nEnd if.")
        condition = node.branches[0][0]
        assert isinstance(condition, ast.Compare)
        assert isinstance(condition.left, ast.SpriteCoordExpr)

    def test_collision(self):
        node = first("Let crashed be sprite bird collides with sprite pipe.")
        assert isinstance(node.value, ast.SpriteCollidesExpr)
        assert (node.value.left, node.value.right) == ("bird", "pipe")

    def test_remove_sprite(self):
        assert isinstance(first("Remove sprite bird."), ast.RemoveSpriteStmt)


class TestCanvas:
    def test_add_canvas(self):
        node = first("Add canvas game area with width 800 and height 600.")
        assert isinstance(node, ast.AddCanvasStmt)
        assert node.name == "game area"

    def test_rectangle(self):
        node = first("Draw rectangle at 10 by 20 with width 50 and height 30 and color red.")
        assert isinstance(node, ast.DrawRectangleStmt)
        assert node.color.value == "red"

    def test_canvas_circle(self):
        node = first("Draw circle at 300 by 150 with radius 20 and color yellow.")
        assert isinstance(node, ast.DrawCanvasCircleStmt)

    def test_turtle_circle_still_works(self):
        assert isinstance(first("Draw circle with radius 40."), ast.DrawCircleStmt)

    def test_canvas_text(self):
        node = first("Draw text Score at 10 by 10 with color white.")
        assert isinstance(node, ast.DrawCanvasTextStmt)
        assert node.text.value == "Score"

    def test_clear_canvas(self):
        assert isinstance(first("Clear canvas."), ast.ClearCanvasStmt)


class TestGames:
    def test_arcade_games(self):
        for kind in ("flappy bird", "snake", "pong", "memory", "jump and run"):
            node = first(f"Start a {kind} game.")
            assert isinstance(node, ast.StartGameStmt)
            assert node.game_type == kind

    def test_unknown_game_is_rejected(self):
        import pytest
        from epp.errors import EppParseError
        with pytest.raises(EppParseError):
            first("Start a chess game.")


class TestWidgets:
    def test_checkbox(self):
        node = first("Add checkbox agree with label I agree.")
        assert isinstance(node, ast.AddCheckboxStmt)
        assert node.label.value == "I agree"

    def test_radio_group_keeps_spelling(self):
        node = first("Add radio group difficulty with options Easy, Medium, Hard.")
        assert node.options == ["Easy", "Medium", "Hard"]

    def test_slider(self):
        node = first("Add slider volume from 0 to 100.")
        assert (node.low.value, node.high.value) == (0, 100)

    def test_image(self):
        node = first("Add image logo from the file logo.png.")
        assert node.file_path.value == "logo.png"

    def test_menu_and_menu_item(self):
        menu = first("Add menu File with options New, Open, Save, Exit.")
        assert (menu.name, menu.options) == ("File", ["New", "Open", "Save", "Exit"])
        item = first("Add menu item Exit in File that calls handle exit.")
        assert (item.item, item.menu, item.fn_name) == ("Exit", "File", "handle exit")

    def test_layout(self):
        assert first("Arrange widgets in a grid with 3 columns.").columns.value == 3
        assert first("Add spacing 10 around all widgets.").amount.value == 10
        align = first("Align label welcome to the center.")
        assert (align.kind, align.name, align.alignment) == ("label", "welcome", "center")

    def test_widget_values(self):
        assert isinstance(first("Let a be the checkbox agree.").value, ast.CheckboxValueExpr)
        assert isinstance(first("Let b be the radio group difficulty.").value, ast.RadioGroupValueExpr)
        assert isinstance(first("Let c be the slider volume.").value, ast.SliderValueExpr)

    def test_dialogs(self):
        node = first("Ask yes or no with the message Do you want to save.")
        assert isinstance(node, ast.AskYesNoStmt)
        assert first("Ask for a file to open.").mode == "open"
        assert first("Ask for a file to save as.").mode == "save"


class TestWebStatements:
    def test_before_every_request(self):
        node = first("Before every request, do the following.\nSay hi.\nEnd before.")
        assert isinstance(node, ast.BeforeRequestStmt)

    def test_set_cookie_and_session(self):
        cookie = first("Set the cookie username of request to Alice.")
        assert (cookie.cookie_name, cookie.request_var) == ("username", "request")
        session = first("Set the session value name in request to Alice.")
        assert (session.key, session.request_var) == ("name", "request")

    def test_start_session(self):
        assert first("Start a session for request.").request_var == "request"

    def test_request_expressions(self):
        assert isinstance(first("Let a be the cookie username of request.").value, ast.CookieExpr)
        assert isinstance(first("Let b be the session value name of request.").value, ast.SessionValueExpr)
        assert isinstance(first("Let c be the form value username of request.").value, ast.FormValueExpr)
        assert isinstance(first("Let d be the uploaded file avatar of request.").value, ast.UploadedFileExpr)

    def test_websocket_statements(self):
        route = first("Add websocket route slash ws to handle chat.")
        assert (route.path, route.handler_name) == ("/ws", "handle chat")
        send = first("Send the value of message to connection.")
        assert send.connection == "connection"
        assert isinstance(first("Broadcast the value of message to all connections."), ast.BroadcastStmt)


class TestPlaceholders:
    def test_placeholder_replacement_node(self):
        node = first("Let page be the value of template with placeholder name replaced by the value of who.")
        assert isinstance(node.value, ast.ReplacePlaceholderExpr)
        assert node.value.placeholder == "name"

    def test_plain_replacement_still_works(self):
        node = first("Let page be the value of template with hello replaced by bye.")
        assert isinstance(node.value, ast.ReplaceExpr)
