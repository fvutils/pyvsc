PYVSC_VE_PERF_COMMON_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
PACKAGES_DIR := $(abspath $(PYVSC_VE_PERF_COMMON_DIR)/../packages)
DV_MK := $(shell PATH=$(PACKAGES_DIR)/python/bin:$(PATH) python3 -m mkdv mkfile)

ifneq (1,$(RULES))

include $(DV_MK)
else # Rules
include $(DV_MK)

endif

