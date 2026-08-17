"""Tests for E++ ML operations (mean, sum, min, max, dot product)."""


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
