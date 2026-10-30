/* dmd_serum: the game's Serum colourisation of its 128x32 DMD for a ZeDMD. Licence: GPL v2 (it links libserum,
 * https://github.com/PPUC/libserum). The DMD is part of the game, so this lives in the game; the platform's zedmd_feed
 * (MPF-Godot-Packaging) stays the plain RGB feeder and knows nothing of Serum.
 *
 * Godot's dmd_out add-on pipes 128x32 RGB frames (12288 bytes, the --zedmd colour scaled by 16 shades) to this program in
 * place of the feeder; it recovers the ROM's shade of every dot, asks libserum for the colours and pipes the RGB frames on to
 * the platform's zedmd_feed (started here, with its stdin and the same stdout/stderr). A frame the colourisation file does not
 * know goes on as it came (the plain colour); colour rotations run on libserum's timer.
 *
 *   dmd_serum --serum DIR --rom NAME --color RRGGBB --feeder PATH [-- feeder arguments]   frames on stdin; ends when it closes
 *   dmd_serum ... --probe     only runs the feeder with --probe and returns its code (0 a ZeDMD answers, 2 none)
 * The same arguments, separated by | in the environment variable DMD_SERUM_ARGS, when the add-on cannot pass them.
 * DIR/NAME/NAME.cROMc is the colourisation file: the player's own, never in the repository. */
#include <errno.h>
#include <poll.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#include <algorithm>
#include <string>
#include <vector>

#include "serum-decode.h"

static const int W = 128, H = 32, DOTS = W * H;
static Serum_Frame_Struc *sf = NULL;

/* RGB565 to RGB888: each channel's top bits repeated into its low bits */
static void to_rgb(const uint16_t *src, uint8_t *rgb) {
    for (int i = 0; i < DOTS; i++) {
        unsigned p = src[i], r = p >> 11 & 31, g = p >> 5 & 63, b = p & 31;
        rgb[i * 3] = r << 3 | r >> 2;
        rgb[i * 3 + 1] = g << 2 | g >> 4;
        rgb[i * 3 + 2] = b << 3 | b >> 2;
    }
}

static int plane(uint8_t *rgb) {
    if (sf->SerumVersion == SERUM_V2) {
        if (!(sf->flags & FLAG_RETURNED_32P_FRAME_OK) || !sf->frame32 || (int)sf->width32 != W) return 0;
        to_rgb(sf->frame32, rgb);
        return 1;
    }
    if (!sf->frame || !sf->palette) return 0;           /* v1: a palette of 64 colours per frame */
    for (int i = 0; i < DOTS; i++) memcpy(rgb + i * 3, sf->palette + sf->frame[i] * 3, 3);
    return 1;
}

/* 1 coloured, 0 unknown to the file (rgb untouched), 2 the same frame as before (rgb untouched) */
static int colorize(const uint8_t *shades, uint8_t *rgb, int *rotate_ms) {
    uint8_t in[256 * 64];
    memcpy(in, shades, DOTS);
    uint32_t r = Serum_Colorize(in);
    *rotate_ms = 0;
    if (r == IDENTIFY_NO_FRAME) return 0;
    if (r == IDENTIFY_SAME_FRAME) return 2;
    *rotate_ms = r & 0xffff;
    return plane(rgb) ? 1 : 0;
}

static std::vector<std::string> split(const char *s) {
    std::vector<std::string> out;
    std::string cur;
    for (; *s; s++) {
        if (*s == '|') { out.push_back(cur); cur.clear(); }
        else cur += *s;
    }
    if (!cur.empty() || !out.empty()) out.push_back(cur);
    return out;
}

static int write_all(int fd, const uint8_t *p, size_t n) {
    while (n) {
        ssize_t w = write(fd, p, n);
        if (w < 0 && errno == EINTR) continue;
        if (w <= 0) return 0;
        p += w;
        n -= w;
    }
    return 1;
}

static pid_t start_feeder(const std::string &path, const std::vector<std::string> &args, int *to_feeder) {
    int fds[2];
    if (pipe(fds)) return -1;
    pid_t pid = fork();
    if (pid == 0) {
        dup2(fds[0], 0);
        close(fds[0]);
        close(fds[1]);
        std::vector<char *> av;
        av.push_back((char *)path.c_str());
        for (auto &a : args) av.push_back((char *)a.c_str());
        av.push_back(NULL);
        execv(path.c_str(), av.data());
        perror("dmd_serum: cannot start the feeder");
        _exit(127);
    }
    close(fds[0]);
    *to_feeder = fds[1];
    return pid;
}

int main(int argc, char **argv) {
    signal(SIGPIPE, SIG_IGN);
    std::vector<std::string> a(argv + 1, argv + argc);
    if (const char *env = getenv("DMD_SERUM_ARGS")) {
        bool probing = std::find(a.begin(), a.end(), "--probe") != a.end();
        a = split(env);
        if (probing) a.push_back("--probe");
    }
    std::string dir, rom, feeder;
    unsigned rgb0 = 0xff730d;
    std::vector<std::string> fargs;
    bool probe = false, rest = false;
    for (size_t i = 0; i < a.size(); i++) {
        if (rest) fargs.push_back(a[i]);
        else if (a[i] == "--") rest = true;
        else if (a[i] == "--serum" && i + 1 < a.size()) dir = a[++i];
        else if (a[i] == "--rom" && i + 1 < a.size()) rom = a[++i];
        else if (a[i] == "--color" && i + 1 < a.size()) rgb0 = strtoul(a[++i].c_str(), NULL, 16);
        else if (a[i] == "--feeder" && i + 1 < a.size()) feeder = a[++i];
        else if (a[i] == "--probe") probe = true;
    }
    if (feeder.empty() || dir.empty() || rom.empty()) {
        fprintf(stderr, "dmd_serum --serum DIR --rom NAME --color RRGGBB --feeder PATH [-- feeder arguments]\n");
        return 1;
    }
    if (probe) {
        fargs.push_back("--probe");
        int fd;
        pid_t pid = start_feeder(feeder, fargs, &fd);
        if (pid < 0) return 1;
        close(fd);
        int st = 0;
        waitpid(pid, &st, 0);
        return WIFEXITED(st) ? WEXITSTATUS(st) : 1;
    }
    sf = Serum_Load(dir.c_str(), rom.c_str(), FLAG_REQUEST_32P_FRAMES);
    if (!sf) {
        fprintf(stderr, "Serum: %s/%s not loaded: %s\n", dir.c_str(), rom.c_str(), Serum_GetLastErrorMessage());
        return 1;
    }
    int out;
    pid_t pid = start_feeder(feeder, fargs, &out);
    if (pid < 0) return 1;

    unsigned top = std::max(rgb0 >> 16 & 255, std::max(rgb0 >> 8 & 255, rgb0 & 255));    /* the colour's brightest channel */
    if (!top) top = 255;
    const size_t fsize = DOTS * 3;
    std::vector<uint8_t> in(fsize * 8), src(fsize), shades(DOTS), last(fsize);
    size_t have = 0;
    bool have_frame = false;
    int rotate_ms = 0;
    struct timespec rot_at = {0, 0};
    for (;;) {
        int wait = 3000;
        if (rotate_ms > 0) {
            struct timespec now;
            clock_gettime(CLOCK_MONOTONIC, &now);
            wait = (rot_at.tv_sec - now.tv_sec) * 1000 + (rot_at.tv_nsec - now.tv_nsec) / 1000000;
            if (wait < 0) wait = 0;
        }
        struct pollfd p = {0, POLLIN, 0};
        bool rotate = false, eof = false, fresh = false;
        if (poll(&p, 1, wait) == 0) {
            if (rotate_ms <= 0) continue;
            rotate = true;
        }
        while (!rotate) {                   /* read what is there; only the newest complete frame is coloured */
            ssize_t r = read(0, in.data() + have, in.size() - have);
            if (r <= 0) { eof = true; break; }
            have += r;
            size_t whole = have / fsize * fsize;
            if (whole) {
                memcpy(src.data(), in.data() + whole - fsize, fsize);
                memmove(in.data(), in.data() + whole, have - whole);
                have -= whole;
                have_frame = fresh = true;
            }
            p.revents = 0;
            if (!(poll(&p, 1, 0) > 0 && have < in.size())) break;
        }
        if (eof && !have_frame) break;
        int known = 0;
        if (rotate) {
            uint32_t r = Serum_Rotate();
            rotate_ms = r & 0xffff;
            plane(last.data());
            known = 1;
        } else if (fresh) {
            for (int i = 0; i < DOTS; i++) {
                unsigned m = std::max(src[i * 3], std::max(src[i * 3 + 1], src[i * 3 + 2]));
                shades[i] = std::min(15u, (m * 15 + top / 2) / top);
            }
            known = colorize(shades.data(), last.data(), &rotate_ms);
            if (known == 0) {
                rotate_ms = 0;
                memcpy(last.data(), src.data(), fsize);     /* unknown to the file: the plain colour, as it came */
            }
        }
        if (rotate_ms > 0) {
            clock_gettime(CLOCK_MONOTONIC, &rot_at);
            rot_at.tv_nsec += (long)rotate_ms * 1000000L;
            rot_at.tv_sec += rot_at.tv_nsec / 1000000000L;
            rot_at.tv_nsec %= 1000000000L;
        }
        if (known != 2 && (rotate || fresh) && !write_all(out, last.data(), fsize)) break;
        if (eof) break;
    }
    close(out);
    waitpid(pid, NULL, 0);
    return 0;
}
