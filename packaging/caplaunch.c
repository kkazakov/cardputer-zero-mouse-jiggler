/* Mouse Jiggler launcher with CAP_NET_BIND_SERVICE.
 *
 * L2CAP PSMs 0x11/0x13 (HID control/interrupt) are privileged, so the app needs
 * CAP_NET_BIND_SERVICE. Instead of running the whole app as root, this launcher
 * carries that single capability as a file capability, moves it into the
 * inheritable+ambient set and execs the system interpreter. The Python process
 * then holds exactly one capability and nothing else.
 *
 * Install:  setcap cap_net_bind_service=pie /usr/lib/mouse-jiggler/caplaunch
 *
 * A file capability only fills the permitted set, and raising it into the
 * ambient set requires it to be inheritable as well — hence the explicit
 * capget/capset round trip before prctl(PR_CAP_AMBIENT_RAISE).
 */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/prctl.h>
#include <sys/syscall.h>
#include <linux/capability.h>

#ifndef PR_CAP_AMBIENT
#define PR_CAP_AMBIENT 47
#define PR_CAP_AMBIENT_RAISE 2
#endif

static int make_ambient(int cap)
{
    struct __user_cap_header_struct hdr;
    struct __user_cap_data_struct data[2];

    memset(&hdr, 0, sizeof(hdr));
    memset(data, 0, sizeof(data));
    hdr.version = _LINUX_CAPABILITY_VERSION_3;

    if (syscall(SYS_capget, &hdr, data) != 0) {
        perror("mouse-jiggler: capget");
        return -1;
    }
    data[0].inheritable |= (unsigned int)(1u << cap);
    if (syscall(SYS_capset, &hdr, data) != 0) {
        perror("mouse-jiggler: capset");
        return -1;
    }
    if (prctl(PR_CAP_AMBIENT, PR_CAP_AMBIENT_RAISE, cap, 0L, 0L) != 0) {
        perror("mouse-jiggler: prctl(PR_CAP_AMBIENT_RAISE)");
        return -1;
    }
    return 0;
}

int main(int argc, char **argv)
{
    static const char *py = "/usr/bin/python3";

    /* CAP_NET_BIND_SERVICE is bit 10 in the first capability word. */
    make_ambient(10);

    char **args = calloc((size_t)argc + 3, sizeof(char *));
    if (!args)
        return 126;

    args[0] = (char *)py;
    args[1] = "-m";
    args[2] = "mouse_jiggler";
    for (int i = 1; i < argc; i++)
        args[i + 2] = argv[i];

    execv(py, args);
    perror("mouse-jiggler: exec python3");
    return 127;
}
