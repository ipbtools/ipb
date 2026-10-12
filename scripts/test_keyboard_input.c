#include "../Sources/keyboard_input.h"
#include <assert.h>
#include <stdio.h>

int main(void) {
    IPBKeyboardState held={0}; uint32_t usages[232];
    assert(ipbKeyboardEmpty(held));
    ipbKeyboardSet(&held,0xe3,true); ipbKeyboardSet(&held,0xe1,true);
    ipbKeyboardSet(&held,ipbKeyboardUsage(0),true); // Command+Shift+A
    assert(ipbKeyboardUsages(held,usages)==3);
    assert(usages[0]==4 && usages[1]==225 && usages[2]==227);
    ipbKeyboardSet(&held,4,false); // key up must preserve held modifiers
    assert(ipbKeyboardUsages(held,usages)==2);
    assert(ipbKeyboardHas(held,225) && ipbKeyboardHas(held,227));
    ipbKeyboardSet(&held,232,true); assert(ipbKeyboardUsages(held,usages)==2);
    assert(ipbKeyboardUsage(36)==40 && ipbKeyboardUsage(51)==42);
    assert(ipbKeyboardUsage(123)==80 && ipbKeyboardUsage(126)==82);
    assert(ipbKeyboardUsage(82)==98 && ipbKeyboardUsage(76)==88);
    assert(ipbKeyboardUsage(999)==0);
    memset(&held,0,sizeof held); assert(ipbKeyboardEmpty(held));
    puts("keyboard input contracts passed (multi-modifier held state, key up, mapping bounds)");
}
