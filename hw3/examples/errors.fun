function f(a: int[]) returns (r: int)
{
  r = a;
  r = unknown;
  if (r) r = 1;
}

function g() returns (b: bool)
{
  b = f(1, 2);
  var b: int;
}
