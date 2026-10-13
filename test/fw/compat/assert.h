/* Stand-in for <assert.h> in the freestanding firmware build.
 *
 * peakrdl-cheader's output includes it and uses static_assert(), which is a
 * keyword in C23 but only a macro in C11 - the header a hosted toolchain
 * supplies is what maps one to the other. There is no libc here, so this one
 * definition is all the header has to provide.
 */
#ifndef UNICORN_TEST_COMPAT_ASSERT_H
#define UNICORN_TEST_COMPAT_ASSERT_H

#define static_assert _Static_assert

#endif
