#ifndef IPB_KEYBOARD_INPUT_H
#define IPB_KEYBOARD_INPUT_H
#include <stdint.h>
#include <stdbool.h>
#include <string.h>

// Mac virtual key codes: shipped HIToolbox/Events.h kVK_ANSI_* / kVK_*.
// HID usages: the captured CoreDevice keyboard descriptor, protocol.md.
static uint32_t ipbKeyboardUsage(unsigned code) {
    static const uint8_t table[128]={
        [0]=4,[1]=22,[2]=7,[3]=9,[4]=11,[5]=10,[6]=29,[7]=27,[8]=6,[9]=25,
        [10]=100,[11]=5,[12]=20,[13]=26,[14]=8,[15]=21,[16]=28,[17]=23,
        [18]=30,[19]=31,[20]=32,[21]=33,[22]=35,[23]=34,[24]=46,[25]=38,
        [26]=36,[27]=45,[28]=37,[29]=39,[30]=48,[31]=18,[32]=24,[33]=47,
        [34]=12,[35]=19,[36]=40,[37]=15,[38]=13,[39]=52,[40]=14,[41]=51,
        [42]=49,[43]=54,[44]=56,[45]=17,[46]=16,[47]=55,[48]=43,[49]=44,
        [50]=53,[51]=42,[53]=41,[54]=231,[55]=227,[56]=225,[57]=57,
        [58]=226,[59]=224,[60]=229,[61]=230,[62]=228,[64]=108,[65]=99,
        [67]=85,[69]=87,[71]=83,[75]=84,[76]=88,[78]=86,[79]=109,[80]=110,
        [81]=103,[82]=98,[83]=89,[84]=90,[85]=91,[86]=92,[87]=93,[88]=94,
        [89]=95,[90]=111,[91]=96,[92]=97,[93]=137,[94]=135,[95]=133,
        [96]=62,[97]=63,[98]=64,[99]=60,[100]=65,[101]=66,[102]=145,
        [103]=68,[104]=144,[105]=104,[106]=107,[107]=105,[109]=67,[111]=69,
        [113]=106,[114]=73,[115]=74,[116]=75,[117]=76,[118]=61,[119]=77,
        [120]=59,[121]=78,[122]=58,[123]=80,[124]=79,[125]=81,[126]=82
    };
    return code<128?table[code]:0;
}
typedef struct { uint64_t bits[4]; } IPBKeyboardState;
static bool ipbKeyboardEmpty(IPBKeyboardState state) {
    return !(state.bits[0]|state.bits[1]|state.bits[2]|state.bits[3]);
}
static bool ipbKeyboardHas(IPBKeyboardState state,uint32_t usage) {
    return usage && usage<=0xe7 && (state.bits[usage/64]&(UINT64_C(1)<<(usage%64)));
}
static void ipbKeyboardSet(IPBKeyboardState *state,uint32_t usage,bool down) {
    if(!usage || usage>0xe7) return;
    uint64_t bit=UINT64_C(1)<<(usage%64);
    if(down) state->bits[usage/64]|=bit; else state->bits[usage/64]&=~bit;
}
static unsigned ipbKeyboardUsages(IPBKeyboardState state,uint32_t usages[232]) {
    unsigned count=0;
    for(uint32_t usage=1;usage<=0xe7;usage++) if(ipbKeyboardHas(state,usage)) usages[count++]=usage;
    return count;
}
#endif
