PyVSC Features
##############

Constraint Features


========================  ======  =============  ===  ===========
Feature                   Py-VSC  SystemVerilog  PSS  Description
<                         Y       Y              Y
>                         Y       Y              Y
<=                        Y       Y              Y
>=                        Y       Y              Y
<=                        Y       Y              Y
>=                        Y       Y              Y
==                        Y       Y              Y
!=                        Y       Y              Y
`+`                       Y       Y              Y
`-`                       Y       Y              Y
`/`                       Y       Y              Y
`*`                       Y       Y              Y
%                         Y       Y              Y
&                         Y       Y              Y
`|`                       Y       Y              Y
&&                        Y       Y              Y
||                        Y       Y              Y
unary |                   N       Y              N
unary &                   N       Y              N
unary ^                   N       Y              N
scalar fixed-size array   N       Y              Y
scalar dynamic array      N       Y              N
class fixed-size array    N       Y              Y
class dynamic array       N       Y              N
class (in)equality        N       N              Y
array sum                 N       Y              Y
array size                N       Y              Y
array reduction OR        N       Y              N
array reduction AND       N       Y              N
array reduction XOR       N       Y              N
part select `[bit]`       N       Y              Y
part select `[msb:lsb]`   N       Y              Y
default                   N       N              Y
dist                      N       Y              N
dynamic                   Y       N              Y
inside (in)               Y       Y              Y
soft                      Y       Y              N
solve before              N       Y              N
unique                    Y       Y              Y
foreach                   N       Y              Y
forall                    N       Y              Y
pre_randomize             Y       Y              Y
post_randomize            Y       Y              Y
constraint override       Y       Y              Y
constraint_mode           Y       Y              N
========================  ======  =============  ===  ===========


Coverage Features


============================  ======  =============  ===  ===========
Feature                       Py-VSC  SystemVerilog  PSS  Description
covergroup type               Y       Y              Y
covergroup inline type        N       N              Y
bins                          Y       Y              Y
ignore_bins                   N       Y              Y
illegal_bins                  N       Y              Y
coverpoint                    Y       Y              Y
coverpoint single bin         Y       Y              Y 
coverpoint array bin          Y       Y              Y 
coverpoint auto bins          N       Y              Y 
coverpoint transition bin     N       Y              N 
cross auto bins               Y       Y              Y
cross bin expressions         N       Y              Y
cross explicit bins           N       Y              Y
cross ignore_bins             N       Y              Y
cross illegal_bins            N       Y              Y
============================  ======  =============  ===  ===========
