function sum(a: int[], n: int) returns (s: int)
  requires n >= 0 && n <= length(a)
  ensures s >= 0
{
  var i: int = 0;
  s = 0;
  while (i < n)
    invariant 0 <= i && i <= n
  {
    s = s + a[i];
    i = i + 1;
  }
}

function fill(a: int[], v: int) returns (b: int[])
{
  b = a;
  var i: int = 0;
  while (i < length(b)) {
    b[i] = v;
    i = i + 1;
  }
  assert length(b) == length(a);
}
