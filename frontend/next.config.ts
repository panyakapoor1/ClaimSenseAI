import path from "path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  turbopack: {
    /**
     * Pin the workspace root to this directory.
     *
     * Next infers the root by walking up for a lockfile, and an unrelated
     * `package-lock.json` in the user's home folder made it choose that instead.
     * Turbopack then watched the whole profile, which is why dev compiles swung
     * between 200ms and 30s. The root exists to bound filesystem watching, so
     * setting it explicitly is the fix rather than a workaround.
     */
    root: path.resolve(__dirname),
  },
};

export default nextConfig;
