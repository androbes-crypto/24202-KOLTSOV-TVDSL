KW_FUNCTION   token  function
KW_RETURNS    token  returns
KW_REQUIRES   token  requires
KW_ENSURES    token  ensures
KW_VAR        token  var
KW_WHILE      token  while
KW_IF         token  if
KW_ELSE       token  else
KW_ASSERT     token  assert
KW_ASSUME     token  assume
KW_INVARIANT  token  invariant
KW_LENGTH     token  length
KW_INT        token  int
KW_BOOL       token  bool
KW_TRUE       token  true
KW_FALSE      token  false

IDENT         token  [A-Za-z_][A-Za-z0-9_]*
INT           token  0|[1-9][0-9]*
BAD_INT       error  0[0-9]+

WS            skip   [ \t\r\n]+
COMMENT       skip   //[^\r\n]*

EQ            token  ==
NE            token  !=
LE            token  <=
GE            token  >=
LT            token  <
GT            token  >
ASSIGN        token  =
AND           token  &&
OR            token  \|\|
NOT           token  !
PLUS          token  \+
MINUS         token  -
STAR          token  \*
SLASH         token  /
PERCENT       token  %

LPAREN        token  \(
RPAREN        token  \)
LBRACKET      token  \[
RBRACKET      token  \]
LBRACE        token  \{
RBRACE        token  \}
COMMA         token  ,
SEMI          token  ;
COLON         token  :
