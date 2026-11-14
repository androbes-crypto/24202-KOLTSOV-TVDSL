function f(x: int, a: int[]) returns (r: int)
{
  if (x > 0) {
    r = a[x] + 1;
  } else {
    r = 0;
  }
}
