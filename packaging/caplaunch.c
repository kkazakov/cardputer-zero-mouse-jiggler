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
 *
 * Exit status:
 *   0..76, 78..  whatever python3 exits with
 *   77           CAP_NET_BIND_SERVICE could not be obtained (no file
 *                capability, nosuid/noexec filesystem, hardened no_new_privs).
 *                bin/mouse-jiggler matches on this to fall back to sudo -n,
 *                so the app still works when the capability is unavailable.
 *
 * `sudo ./install.sh doctor` checks this whole chain end to end.
 */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/prctl.h>
#include <sys/syscall.h>
#include <linux/capability.h>

#define CAP_NET_BIND_SERVICE_BIT 10
#define EXIT_NO_CAPABILITY 77

#ifndef PR_CAP_AMBIENT
#define PR_CAP_AMBIENT 47
#define PR_CAP_AMBIENT_RAISE 2
#endif

static void explain(void)
{
    fputs("mouse-jiggler: cannot raise CAP_NET_BIND_SERVICE into the ambient set,\n"
          "               so the HID L2CAP PSMs (17/19) cannot be bound.\n"
          "               The launcher needs a file capability on a filesystem that\n"
          "               actually carries it:\n"
          "                 sudo setcap cap_net_bind_service=pie "
          "/usr/lib/mouse-jiggler/caplaunch\n"
          "                 getcap /usr/lib/mouse-jiggler/caplaunch\n"
          "               a nosuid/read-only filesystem silently drops it.\n"
          "               `sudo ./install.sh doctor` checks this end to end.\n",
          stderr);
}

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
    if (!(data[0].permitted & (1u << cap))) {
        fputs("mouse-jiggler: CAP_NET_BIND_SERVICE is not in the permitted set "
              "(no file capability)\n", stderr);
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

    if (make_ambient(CAP_NET_BIND_SERVICE_BIT) != 0) {
        explain();
        return EXIT_NO_CAPABILITY;
    }

    char **args = calloc((size_t)argc + 3, sizeof(char *));
    if (!args) {
        perror("mouse-jiggler: calloc");
        return 126;
    }

    args[0] = (char *)py;
    args[1] = "-m";
    args[2] = "mouse_jiggler";
    for (int i = 1; i < argc; i++)
        args[i + 2] = argv[i];

    execv(py, args);
    perror("mouse-jiggler: exec python3");
    return 127;
}
