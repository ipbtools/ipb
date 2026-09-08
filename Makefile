# Defaults to the selected Xcode (honours DEVELOPER_DIR); override with XCODE_PATH=/path/to/Xcode.app
XCODE_PATH ?= $(patsubst %/Contents/Developer,%,$(shell xcode-select -p))
SDK_PRIVATE_FRAMEWORKS := $(XCODE_PATH)/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk/System/Library/PrivateFrameworks

BUILD_DIR := build
SOURCES_DIR := Sources
TARGET := $(BUILD_DIR)/ipb-helper
VIDEO_TARGET := $(BUILD_DIR)/ipb-video
MIRROR_TARGET := $(BUILD_DIR)/ipb-mirror-probe
MIRROR_GLUE = $(filter-out $(BUILD_DIR)/ipb-helper.o,$(OBJS))

OBJS := \
	$(BUILD_DIR)/ipb-helper.o \
	$(BUILD_DIR)/mercury_glue.o \
	$(BUILD_DIR)/mercury_abi.o \
	$(BUILD_DIR)/universalhid_glue.o \
	$(BUILD_DIR)/universalhid_abi.o \
	$(BUILD_DIR)/uhid_request_abi.o

PREFIX ?= /usr/local

.PHONY: all clean smoke install

all: $(TARGET) $(VIDEO_TARGET) $(MIRROR_TARGET)

$(BUILD_DIR):
	mkdir -p $@

$(BUILD_DIR)/ipb-helper.o: $(SOURCES_DIR)/action_sender.m | $(BUILD_DIR)
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


$(VIDEO_TARGET): $(SOURCES_DIR)/video_stream.m | $(BUILD_DIR)
	clang -fobjc-arc \
		-o $@ $< \
		-framework Foundation -framework CoreMedia -framework CoreVideo -lobjc \
		-Xlinker -undefined -Xlinker dynamic_lookup
	codesign -s - -f $@ >/dev/null 2>&1 || true   # in-process path needs no entitlement

# M1 evidence probe: reuse released Swift/assembly glue; no action_sender main.
$(BUILD_DIR)/mirror_probe.o: Experiments/mirror/mirror_probe.m | $(BUILD_DIR)
	clang -fobjc-arc -fblocks -Wall -Wextra -Wno-unused-parameter \
		-c $< -o $@

$(MIRROR_TARGET): $(BUILD_DIR)/mirror_probe.o $(MIRROR_GLUE)
	swiftc $^ -o $@ \
		-F/Library/Developer/PrivateFrameworks \
		-F/Library/Developer/PrivateFrameworks/CoreDevice.framework/Frameworks \
		-F/Library/Apple/System/Library/PrivateFrameworks \
		-F$(SDK_PRIVATE_FRAMEWORKS) \
		-framework Foundation -framework CoreFoundation \
		-framework CoreMedia -framework CoreVideo \
		-framework CoreDevice -framework CoreDeviceUtilities \
		-framework RemoteXPC -framework Mercury -framework UniversalHID \
		-Xlinker -undefined -Xlinker dynamic_lookup
	codesign -s - -f $@

smoke: all
	bin/ipb screenshot $(BUILD_DIR)/smoke.png

install: all
	install -d $(PREFIX)/bin $(PREFIX)/libexec $(PREFIX)/share/ipb
	install -m 755 bin/ipb $(PREFIX)/bin/ipb
	install -m 755 $(TARGET) $(PREFIX)/libexec/ipb-helper
	install -m 755 $(VIDEO_TARGET) $(PREFIX)/libexec/ipb-video
	codesign -s - -f $(PREFIX)/libexec/ipb-video >/dev/null 2>&1 || true
	install -m 644 VERSION $(PREFIX)/share/ipb/VERSION
	install -m 755 scripts/smoke_matrix.sh $(PREFIX)/share/ipb/smoke_matrix.sh

clean:
	rm -rf $(BUILD_DIR)
