Throwaway hand-off (no PR, never main). GoZen arm64 for the Raspberry Pi 4.
Tree: GDE GoZen f9448619 + scripts/gozen/gozen{,_v4l2m2m,_v4l2m2m_flush}.patch + gozen_zerocopy.patch + num_capture_buffers 12
(= libgozen 7559ebeb) + NV12 on v4l2m2m (GOZEN_V4L2_PIXFMT=yuv420p restores three planes).
FFmpeg 5a1f107b (7.1) vanilla, lean, v4l2m2m on, no jetson-ffmpeg (no nvmpi decoders: unused on the Pi).
Cross-built on x86_64, aarch64-linux-gnu-gcc 13.3, max GLIBC_2.38. gozen_full_vs_base.patch = diff against base (f9448619 + 3 patches).
