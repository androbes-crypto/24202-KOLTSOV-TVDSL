function expr(a: int, b: int, c: int, d: int) returns (r: int)
{
  var x = a + b;
  var y = x + x;          // a + b is computed once (cse)
  r = (a + b) * (c - d * 2) + (a - b) * (c + d) + y * 1;
}
