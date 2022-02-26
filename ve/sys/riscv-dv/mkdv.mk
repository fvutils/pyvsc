MKDV_MK:=$(abspath $(lastword $(MAKEFILE_LIST)))
TEST_DIR:=$(dir $(MKDV_MK))
PYVSC_DIR := $(abspath $(TEST_DIR)/../../..)
PACKAGES_DIR := $(PYVSC_DIR)/packages
MKDV_TOOL = none
DV_MK:=$(shell $(PACKAGES_DIR)/python/bin/python3 -m mkdv mkfile)

TEST ?= riscv_floating_point_arithmetic_test
ITERATION ?= 1
TARGET ?= rv32imafdc
STEPS ?= gen

MKDV_PYTHONPATH += $(PYVSC_DIR)/src
MKDV_PYTHONPATH += $(PACKAGES_DIR)/riscv-dv/pygen

# riscv-dv assumes the 'right' Python is in the path
PATH:=$(PACKAGES_DIR)/python/bin:$(PATH)
export PATH

ifneq (,$(TARGET))
  ARGS += --target $(TARGET)
endif

MKDV_RUN_DEPS += gentest
include $(DV_MK)

RULES:=1
include $(DV_MK)


gentest :
	$(PACKAGES_DIR)/python/bin/python3 \
		$(PACKAGES_DIR)/riscv-dv/run.py \
		--test $(TEST) \
		--iteration $(ITERATION) \
		--simulator pyflow \
		--steps $(STEPS) \
		$(ARGS)

