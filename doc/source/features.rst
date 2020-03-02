PyVSC Features
##############

Constraint Features


========================  ======  =============  ===========
Feature                   Py-VSC  SystemVerilog  Description
<                         Y       Y              X
>                         Y       Y              X
<=                        Y       Y              X
>=                        Y       Y              X
<=                        Y       Y              X
>=                        Y       Y              X
==                        Y       Y              X
!=                        Y       Y              X
`+`                       Y       Y              X
`-`                       Y       Y              X
/                         Y       Y              X
`*`                       Y       Y              X
%                         Y       Y              X
&                         Y       Y              X
`|`                       Y       Y              X
&&                        Y       Y              X
||                        Y       Y              X
unary |                   N       Y
unary &                   N       Y
unary ^                   N       Y
scalar fixed-size array   N       Y 
scalar dynamic array      N       Y 
class fixed-size array    N       Y 
class dynamic array       N       Y 
array sum                 N       Y 
array size                N       Y 
array reduction OR        N       Y 
array reduction AND       N       Y 
array reduction XOR       N       Y 
part select `[bit]`       N       Y
part select `[msb:lsb]`   N       Y
default                   N       N              X
dist                      N       Y              X
dynamic                   N       N              X
inside                    Y       Y              X
soft                      N       Y              X
solve before              N       Y              X
unique                    Y       Y              X
foreach                   N       Y              X
pre_randomize             N       Y              X
post_randomize            N       Y              X
constraint override       Y       Y  
constraint_mode           N       Y  
========================  ======  =============  ===========

