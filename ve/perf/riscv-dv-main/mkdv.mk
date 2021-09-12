#****************************************************************************
#* mkdv.mk
#****************************************************************************
MKDV_MK:=$(abspath $(lastword $(MAKEFILE_LIST)))
TEST_DIR := $(dir $(MKDV_MK))
MKDV_TOOL=none

RISCV_DV_VERSION ?= main
PYVSC_VERSION ?= 0.5.5

MKDV_RUN_DEPS += run-target

MKDV_PYTHONPATH += $(PACKAGES_DIR)/pyvsc_$(PYVSC_VERSION)/src
MKDV_PYTHONPATH += $(PACKAGES_DIR)/riscv-dv-$(RISCV_DV_VERSION)/pygen

include $(TEST_DIR)/../common/defs_rules.mk

RULES := 1

.PHONY: run-target
run-target :
	$(PACKAGES_DIR)/python/bin/python3 \
		$(PACKAGES_DIR)/riscv-dv-$(RISCV_DV_VERSION)/run.py \
		--test=riscv_arithmetic_basic_test --iteration 1 \
		--steps gen \
		--simulator pyflow --gen_timeout 3000 --seed 0

include $(TEST_DIR)/../common/defs_rules.mk

