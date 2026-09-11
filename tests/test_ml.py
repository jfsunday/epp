"""Tests for E++ ML operations (mean, sum, min, max, dot product, exp, log, random decimal)."""

import pytest
from epp.errors import EppRuntimeError


class TestMLOperations:
    def test_mean(self, run):
        _, out = run("""
Create a list called nums.
Add 10 to nums.
Add 20 to nums.
Add 30 to nums.
Say the mean of nums.
""")
        assert out == ["20"]

    def test_sum(self, run):
        _, out = run("""
Create a list called nums.
Add 5 to nums.
Add 15 to nums.
Add 30 to nums.
Say the sum of nums.
""")
        assert out == ["50"]

    def test_min(self, run):
        _, out = run("""
Create a list called nums.
Add 42 to nums.
Add 7 to nums.
Add 99 to nums.
Say the min of nums.
""")
        assert out == ["7"]

    def test_max(self, run):
        _, out = run("""
Create a list called nums.
Add 42 to nums.
Add 7 to nums.
Add 99 to nums.
Say the max of nums.
""")
        assert out == ["99"]

    def test_dot_product(self, run):
        _, out = run("""
Create a list called a.
Add 1 to a.
Add 2 to a.
Add 3 to a.
Create a list called b.
Add 4 to b.
Add 5 to b.
Add 6 to b.
Say the dot product of a and b.
""")
        # 1*4 + 2*5 + 3*6 = 4 + 10 + 18 = 32
        assert out == ["32"]

    def test_mean_in_expression(self, run):
        _, out = run("""
Create a list called scores.
Add 80 to scores.
Add 90 to scores.
Add 100 to scores.
Let avg be the mean of scores.
If the value of avg is greater than 85,
    Say above average.
End if.
""")
        assert out == ["above average"]

    def test_exponential_of_zero(self, run):
        _, out = run("Let x be the exponential of 0.\nSay the value of x.")
        assert out == ["1"]

    def test_exponential_of_one(self, run):
        _, out = run("Let x be the exponential of 1.\nSay the value of x.")
        assert float(out[0]) == pytest.approx(2.718281828, rel=1e-6)

    def test_logarithm_of_one(self, run):
        _, out = run("Let x be the logarithm of 1.\nSay the value of x.")
        assert out == ["0"]

    def test_logarithm_of_e(self, run):
        _, out = run("""Let e be the exponential of 1.
Let x be the logarithm of the value of e.
Say the value of x.""")
        assert float(out[0]) == pytest.approx(1.0, rel=1e-6)

    def test_logarithm_negative_error(self, run):
        with pytest.raises(EppRuntimeError):
            run("Let x be the logarithm of 0.")

    def test_exponential_in_expression(self, run):
        _, out = run("""Let x be the exponential of 2.
Let y be the logarithm of the value of x.
Say the value of y.""")
        assert float(out[0]) == pytest.approx(2.0, rel=1e-6)

    def test_random_decimal(self, run):
        _, out = run("Let r be a random decimal between 0 and 1.\nSay the value of r.")
        val = float(out[0])
        assert 0.0 <= val <= 1.0

    def test_random_decimal_range(self, run):
        _, out = run("""Let r be a random decimal between 5 and 10.
Say the value of r.""")
        val = float(out[0])
        assert 5.0 <= val <= 10.0

    def test_random_decimal_negative(self, run):
        _, out = run("""Let r be a random decimal between negative 1 and 1.
Say the value of r.""")
        val = float(out[0])
        assert -1.0 <= val <= 1.0
