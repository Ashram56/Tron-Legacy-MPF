Throwaway hand-off (no PR, never main). Godot 4.6.3-stable editor, linuxbsd arm64, with godot-egl-release-current.patch
(EGLManager::release_current() clears current_window: fixes --render-thread separate on OpenGL ES / EGL).
scons platform=linuxbsd arch=arm64 target=editor production=yes lto=none use_static_cpp=yes (no LTO, unlike the official build),
cross-built with aarch64-linux-gnu-gcc 13.3 (Ubuntu 24.04), max GLIBC_2.38. x11 + wayland, GLES3 + Vulkan.
Unpack: xz -dk Godot_v4.6.3-stable-eglmt_linux.arm64.xz && sha256sum -c Godot_v4.6.3-stable-eglmt_linux.arm64.sha256
