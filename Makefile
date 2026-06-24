XCODE_PATH ?= /Applications/Xcode-27.0.0-Beta.2.app
SDK_PRIVATE_FRAMEWORKS := $(XCODE_PATH)/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk/System/Library/PrivateFrameworks

BUILD_DIR := build
SOURCES_DIR := Sources
TARGET := $(BUILD_DIR)/action_sender_mercury

OBJS := \
	$(BUILD_DIR)/action_sender_mercury.o \
	$(BUILD_DIR)/mercury_glue.o \
	$(BUILD_DIR)/mercury_abi.o \
	$(BUILD_DIR)/universalhid_glue.o \
	$(BUILD_DIR)/universalhid_abi.o \
	$(BUILD_DIR)/uhid_request_abi.o

.PHONY: all clean smoke

all: $(TARGET)

$(BUILD_DIR):
	mkdir -p $@

$(BUILD_DIR)/action_sender_mercury.o: $(SOURCES_DIR)/action_sender.m | $(BUILD_DIR)
	clang -fno-objc-arc -fblocks \
		-F/Library/Developer/PrivateFrameworks \
		-F$(SDK_PRIVATE_FRAMEWORKS) \
		-c $< -o $@

$(BUILD_DIR)/mercury_abi.o: $(SOURCES_DIR)/mercury_abi.S | $(BUILD_DIR)
	clang -c $< -o $@

$(BUILD_DIR)/universalhid_abi.o: $(SOURCES_DIR)/universalhid_abi.S | $(BUILD_DIR)
	clang -c $< -o $@

$(BUILD_DIR)/uhid_request_abi.o: $(SOURCES_DIR)/uhid_request_abi.S | $(BUILD_DIR)
	clang -c $< -o $@

$(BUILD_DIR)/mercury_glue.o: $(SOURCES_DIR)/mercury_glue.swift | $(BUILD_DIR)
	swiftc -parse-as-library -c $< -o $@

$(BUILD_DIR)/universalhid_glue.o: $(SOURCES_DIR)/universalhid_glue.swift | $(BUILD_DIR)
	swiftc -parse-as-library -c $< -o $@

$(TARGET): $(OBJS)
	swiftc $(OBJS) \
		-o $@ \
		-F/Library/Developer/PrivateFrameworks \
		-F/Library/Developer/PrivateFrameworks/CoreDevice.framework/Frameworks \
		-F/Library/Apple/System/Library/PrivateFrameworks \
		-F$(SDK_PRIVATE_FRAMEWORKS) \
		-framework Foundation \
		-framework CoreFoundation \
		-framework CoreDevice \
		-framework CoreDeviceUtilities \
		-framework RemoteXPC \
		-framework Mercury \
		-framework UniversalHID

smoke: all
	bin/devicehubctl screenshot $(BUILD_DIR)/smoke.png

clean:
	rm -rf $(BUILD_DIR)
