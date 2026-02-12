from src.domain.validators import validate_answer


class TestValidateBool:
    def test_si_is_valid(self):
        ok, msg = validate_answer("sí", "bool")
        assert ok is True
        assert msg is None

    def test_si_without_accent_is_valid(self):
        ok, msg = validate_answer("si", "bool")
        assert ok is True

    def test_no_is_valid(self):
        ok, msg = validate_answer("No", "bool")
        assert ok is True
        assert msg is None

    def test_claro_is_valid(self):
        ok, msg = validate_answer("claro", "bool")
        assert ok is True

    def test_nop_is_valid(self):
        ok, msg = validate_answer("nop", "bool")
        assert ok is True

    def test_ambiguous_is_invalid(self):
        ok, msg = validate_answer("quizás", "bool")
        assert ok is False
        assert msg is not None
        assert "sí o no" in msg

    def test_random_text_is_invalid_for_bool(self):
        ok, msg = validate_answer("tengo un perro", "bool")
        assert ok is False


class TestValidateNumber:
    def test_pure_number_is_valid(self):
        ok, msg = validate_answer("3200", "number")
        assert ok is True
        assert msg is None

    def test_number_with_text_is_valid(self):
        ok, msg = validate_answer("Entre 2500 y 3000 EUR", "number")
        assert ok is True

    def test_two_persons_is_valid(self):
        ok, msg = validate_answer("Somos 4", "number")
        assert ok is True

    def test_no_digits_is_invalid(self):
        ok, msg = validate_answer("muchos", "number")
        assert ok is False
        assert msg is not None
        assert "numérico" in msg


class TestValidateText:
    def test_any_text_is_valid(self):
        ok, msg = validate_answer("Tengo un perro mediano mestizo", "text")
        assert ok is True
        assert msg is None

    def test_single_word_is_valid(self):
        ok, msg = validate_answer("Sanidad", "text")
        assert ok is True


class TestValidateEmpty:
    def test_empty_string_is_invalid(self):
        ok, msg = validate_answer("", "text")
        assert ok is False
        assert msg is not None

    def test_whitespace_only_is_invalid(self):
        ok, msg = validate_answer("   ", "bool")
        assert ok is False

    def test_empty_number_is_invalid(self):
        ok, msg = validate_answer("", "number")
        assert ok is False
