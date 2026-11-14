function f(x: int, a: bool[]) returns (r: int)
{
  var n = x + 1;
  var positive;
  positive = n > 0;
  var copy;
  copy = a;
  var first = copy[0];
  if (first || positive) r = n; else r = 0;
}
