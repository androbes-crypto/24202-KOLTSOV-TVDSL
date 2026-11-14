// const + alg + cse + dce + unreach
function calc(a: int, b: int) returns (r: int)
{
  var k = 3;
  var m = k + 4;            // 7
  var big = m < 10;         // true
  var x = a * 1 + 0;        // a
  var u = (a + b) * (a + b);
  var dead = x * m;         // never used
  if (big) {
    r = u + m;
  } else {
    r = a / b;              // unreachable after folding
  }
}

function count(a: int[], v: int) returns (c: int)
{
  var i = 0;
  c = 0;
  while (i < length(a) && a[i] != v) {
    var t = i * 2;          // dead
    c = c + 1;
    i = i + 1;
  }
}
