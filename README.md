# UVM DEBUG

create python api for debug systemverilog uvm testcase.

## install
- vcs
CFLAGS="-DVCS -I $VCS_HOME/include" pip install .
- xcelium
CFLAGS="-DXCELIUM -I $XRUN_HOME/include" pip install .                                                                              
- mentor
CFLAGS="-DMENTOR -I $MENTOR_HOME/include" pip install .                                                                              


## **NOTE**

set_config_int/get_config_int 的另一侧需要使用uvm_bitstream_t  
