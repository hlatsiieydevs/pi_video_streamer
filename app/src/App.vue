<template>
  <div class="min-h-screen bg-slate-950 text-slate-100 pb-16">
    <!-- Header Navbar -->
    <header class="sticky top-0 z-50 glass-panel border-b border-slate-800/80 px-4 py-3 sm:px-6">
      <div class="max-w-7xl mx-auto flex items-center justify-between">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-cyan-500 to-blue-600 flex items-center justify-center shadow-lg shadow-cyan-500/20">
            <Camera class="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 class="text-lg font-bold tracking-tight text-white font-heading flex items-center gap-2">
              Basic Video Streamer
              <span class="text-xs px-2 py-0.5 rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 font-normal">v1.5 Sync-RTSP</span>
            </h1>
            <p class="text-xs text-slate-400">Raspberry Pi 5 High-Performance RTSP Camera Streamer</p>
          </div>
        </div>

        <div class="flex items-center gap-3">
          <button 
            @click="fetchCameras" 
            class="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition flex items-center gap-1.5 text-xs font-medium"
            title="Refresh Status"
          >
            <RefreshCw class="w-4 h-4" :class="{ 'animate-spin': loading }" />
            <span class="hidden sm:inline">Refresh</span>
          </button>
          
          <div class="flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-medium">
            <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            <span>RTSP Server Active</span>
          </div>
        </div>
      </div>
    </header>

    <main class="max-w-7xl mx-auto px-4 py-6 sm:px-6 space-y-6">
      <!-- Camera Selector Tabs -->
      <div class="flex items-center justify-between bg-slate-900/80 p-1.5 rounded-xl border border-slate-800">
        <div class="flex items-center gap-2 overflow-x-auto">
          <button 
            v-for="cam in cameras" 
            :key="cam.id"
            @click="activeCamId = cam.id"
            class="px-4 py-2 rounded-lg font-medium text-xs sm:text-sm transition flex items-center gap-2 whitespace-nowrap"
            :class="activeCamId === cam.id 
              ? 'bg-gradient-to-r from-cyan-600 to-blue-600 text-white shadow-md shadow-cyan-600/30' 
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'"
          >
            <Video class="w-4 h-4" />
            <span>{{ cam.name }}</span>
            <span class="px-1.5 py-0.5 text-[10px] rounded font-mono bg-cyan-500/20 text-cyan-300">
              H.264 (UNIX Sync)
            </span>
          </button>
        </div>

        <div class="hidden md:flex items-center gap-2 text-xs text-slate-400 pr-2 font-mono">
          <Globe class="w-3.5 h-3.5 text-cyan-400" />
          <span>RTP Timestamp Sync Active</span>
        </div>
      </div>

      <!-- Main Active Camera Grid -->
      <div v-if="activeCam" class="grid grid-cols-1 lg:grid-cols-12 gap-6">
        
        <!-- LEFT COLUMN: Live Preview Feed & Key Live Metrics (7 cols) -->
        <div class="lg:col-span-7 space-y-6">
          
          <!-- Live Preview Player Card -->
          <div class="glass-panel rounded-2xl overflow-hidden border border-slate-800 shadow-2xl">
            <div class="px-4 py-3 border-b border-slate-800/80 flex items-center justify-between bg-slate-900/60">
              <div class="flex items-center gap-2">
                <span class="w-2.5 h-2.5 rounded-full bg-red-500 animate-pulse"></span>
                <h2 class="text-sm font-semibold text-white flex items-center gap-2">
                  LIVE PREVIEW - {{ activeCam.name }}
                </h2>
              </div>
              
              <div class="flex items-center gap-2">
                <span class="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                  {{ activeCam.resolution.width }}x{{ activeCam.resolution.height }}
                </span>
                <span class="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-800 text-emerald-400 border border-slate-700">
                  {{ activeCam.fps.actual }} FPS
                </span>
              </div>
            </div>

            <!-- Video Frame Container -->
            <div class="relative bg-black aspect-video flex items-center justify-center overflow-hidden group">
              <img 
                :src="`/video_feed/${activeCam.id}?t=${feedTimestamp}`" 
                class="w-full h-full object-contain"
                alt="Camera Live Stream"
              />
              
              <!-- Video Overlay Watermark/Badges -->
              <div class="absolute top-3 left-3 flex flex-wrap gap-2 pointer-events-none">
                <span class="px-2.5 py-1 rounded-md bg-slate-950/80 backdrop-blur text-cyan-400 text-xs font-mono font-medium border border-cyan-500/30 flex items-center gap-1.5">
                  <Film class="w-3.5 h-3.5" />
                  H.264 (RTSP)
                </span>
                <span v-if="activeCam.sync_telemetry" class="px-2.5 py-1 rounded-md bg-slate-950/80 backdrop-blur text-emerald-400 text-xs font-mono font-medium border border-emerald-500/30 flex items-center gap-1">
                  <Clock class="w-3.5 h-3.5" />
                  UNIX: {{ activeCam.sync_telemetry.timestamp }}
                </span>
                <span v-if="activeCam.orientation.mode !== 'Normal (0°)'" class="px-2.5 py-1 rounded-md bg-amber-950/80 backdrop-blur text-amber-400 text-xs font-mono font-medium border border-amber-500/30 flex items-center gap-1">
                  <RotateCw class="w-3 h-3" />
                  {{ activeCam.orientation.mode }}
                </span>
                <span v-if="activeCam.crop.enabled" class="px-2.5 py-1 rounded-md bg-emerald-950/80 backdrop-blur text-emerald-400 text-xs font-mono font-medium border border-emerald-500/30 flex items-center gap-1">
                  <Crop class="w-3 h-3" />
                  {{ activeCam.crop.preset }}
                </span>
              </div>

              <div class="absolute bottom-3 right-3 pointer-events-none">
                <span class="px-2.5 py-1 rounded-md bg-slate-950/80 backdrop-blur text-slate-300 text-xs font-mono border border-slate-700">
                  {{ activeCam.hardware.is_simulated ? 'SIMULATED FEED' : 'HARDWARE CSI' }}
                </span>
              </div>
            </div>

            <!-- RTSP Link Bar -->
            <div class="p-3 bg-slate-900/90 border-t border-slate-800 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-2">
              <div class="flex items-center gap-2 overflow-hidden text-xs">
                <span class="font-semibold text-slate-400 font-mono text-[11px] uppercase tracking-wider">RTSP URL:</span>
                <code class="text-cyan-300 bg-slate-950 px-2 py-1 rounded border border-slate-800 font-mono text-xs truncate">
                  {{ activeCam.rtsp_url }}
                </code>
              </div>
              <button 
                @click="copyRtspUrl(activeCam.rtsp_url)" 
                class="px-3 py-1.5 rounded-lg bg-cyan-600/20 hover:bg-cyan-600/30 text-cyan-300 border border-cyan-500/30 text-xs font-medium transition flex items-center justify-center gap-1.5 shrink-0"
              >
                <Copy class="w-3.5 h-3.5" />
                <span>{{ copied ? 'Copied!' : 'Copy RTSP' }}</span>
              </button>
            </div>
          </div>

          <!-- Key Live Telemetry Cards Grid -->
          <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div class="glass-card rounded-xl p-3 border border-slate-800">
              <div class="flex items-center justify-between text-slate-400 text-xs mb-1">
                <span>Bitrate</span>
                <Activity class="w-3.5 h-3.5 text-cyan-400" />
              </div>
              <div class="text-base font-bold text-white font-mono">
                {{ activeCam.bitrate.enabled ? activeCam.bitrate.name : 'Auto' }}
              </div>
              <div class="text-[10px] text-slate-400 font-mono">2048kbps Target</div>
            </div>

            <div class="glass-card rounded-xl p-3 border border-slate-800">
              <div class="flex items-center justify-between text-slate-400 text-xs mb-1">
                <span>Framerate</span>
                <Zap class="w-3.5 h-3.5 text-emerald-400" />
              </div>
              <div class="text-base font-bold text-white font-mono">
                {{ activeCam.fps.actual }} <span class="text-xs font-normal text-slate-400">FPS</span>
              </div>
              <div class="text-[10px] text-slate-400">Target 30 FPS</div>
            </div>

            <div class="glass-card rounded-xl p-3 border border-slate-800">
              <div class="flex items-center justify-between text-slate-400 text-xs mb-1">
                <span>Frame Age</span>
                <Clock class="w-3.5 h-3.5 text-emerald-400" />
              </div>
              <div class="text-base font-bold text-emerald-300 font-mono">
                {{ activeCam.sync_telemetry ? activeCam.sync_telemetry.frame_age_ms + ' ms' : '0 ms' }}
              </div>
              <div class="text-[10px] text-slate-400">Microsecond Frame Sync</div>
            </div>

            <div class="glass-card rounded-xl p-3 border border-slate-800">
              <div class="flex items-center justify-between text-slate-400 text-xs mb-1">
                <span>Orientation</span>
                <RotateCw class="w-3.5 h-3.5 text-purple-400" />
              </div>
              <div class="text-xs font-bold text-white font-mono truncate">
                {{ activeCam.orientation.mode }}
              </div>
              <div class="text-[10px] text-slate-400">Camera Mounting</div>
            </div>
          </div>

          <!-- Section 3: Hardware Camera Information Panel -->
          <div class="glass-panel rounded-2xl p-5 border border-slate-800 space-y-4">
            <div class="flex items-center justify-between border-b border-slate-800 pb-3">
              <div class="flex items-center gap-2">
                <Cpu class="w-5 h-5 text-cyan-400" />
                <h3 class="text-base font-semibold text-white font-heading">3. Hardware Camera Information</h3>
              </div>
              <span class="text-xs text-slate-400 font-mono">RPi Direct Sensor Telemetry</span>
            </div>

            <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
              <div class="bg-slate-900/80 p-3 rounded-xl border border-slate-800/80 space-y-1">
                <span class="text-[11px] text-slate-400 font-mono uppercase tracking-wider">3.1 Sensor Model</span>
                <div class="text-sm font-semibold text-cyan-300 font-mono truncate">{{ activeCam.hardware.model }}</div>
              </div>

              <div class="bg-slate-900/80 p-3 rounded-xl border border-slate-800/80 space-y-1">
                <span class="text-[11px] text-slate-400 font-mono uppercase tracking-wider">3.2 Sensor Size</span>
                <div class="text-sm font-semibold text-slate-200 font-mono">{{ activeCam.hardware.sensor_size }}</div>
              </div>

              <div class="bg-slate-900/80 p-3 rounded-xl border border-slate-800/80 space-y-1">
                <span class="text-[11px] text-slate-400 font-mono uppercase tracking-wider">3.3 Shutter Speed</span>
                <div class="text-sm font-semibold text-emerald-400 font-mono">{{ activeCam.hardware.shutter_speed }}</div>
              </div>

              <div class="bg-slate-900/80 p-3 rounded-xl border border-slate-800/80 space-y-1">
                <span class="text-[11px] text-slate-400 font-mono uppercase tracking-wider">3.4 Aperture</span>
                <div class="text-sm font-semibold text-amber-300 font-mono">{{ activeCam.hardware.aperture }}</div>
              </div>

              <div class="bg-slate-900/80 p-3 rounded-xl border border-slate-800/80 space-y-1">
                <span class="text-[11px] text-slate-400 font-mono uppercase tracking-wider">3.5 Frame UNIX Epoch</span>
                <div class="text-xs font-semibold text-purple-400 font-mono truncate">
                  {{ activeCam.sync_telemetry ? activeCam.sync_telemetry.timestamp : '0.000' }}
                </div>
              </div>

              <div class="bg-slate-900/80 p-3 rounded-xl border border-slate-800/80 space-y-1">
                <span class="text-[11px] text-slate-400 font-mono uppercase tracking-wider">Hardware State</span>
                <div class="text-xs font-medium font-mono" :class="activeCam.hardware.is_simulated ? 'text-amber-400' : 'text-emerald-400'">
                  {{ activeCam.hardware.is_simulated ? 'Simulated Generator' : 'Picamera2 Active' }}
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- RIGHT COLUMN: Interactive Camera Controls (5 cols) -->
        <div class="lg:col-span-5 space-y-6">
          
          <!-- Camera Power / Enable Card -->
          <div class="glass-panel rounded-2xl p-5 border border-slate-800 space-y-4">
            <div class="flex items-center justify-between border-b border-slate-800 pb-3">
              <div class="flex items-center gap-2">
                <Power class="w-5 h-5" :class="activeCam.enabled ? 'text-emerald-400' : 'text-red-400'" />
                <h3 class="text-base font-semibold text-white font-heading">Camera Power</h3>
              </div>
              <label class="relative inline-flex items-center cursor-pointer">
                <input 
                  type="checkbox" 
                  :checked="activeCam.enabled" 
                  @change="updateConfig({ enabled: !activeCam.enabled })"
                  class="sr-only peer"
                >
                <div class="w-9 h-5 bg-slate-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-emerald-600"></div>
              </label>
            </div>
            <div class="text-xs text-slate-400">
              Toggle this switch to completely disable or enable this camera stream on the network.
            </div>
          </div>

          <!-- Orientation & Flip Controls Card -->
          <div class="glass-panel rounded-2xl p-5 border border-slate-800 space-y-4">
            <div class="flex items-center justify-between border-b border-slate-800 pb-3">
              <div class="flex items-center gap-2">
                <RotateCw class="w-5 h-5 text-amber-400" />
                <h3 class="text-base font-semibold text-white font-heading">Camera Orientation & Flips</h3>
              </div>
              <span class="text-xs text-amber-400 font-mono">Mounting Adjustment</span>
            </div>

            <!-- Quick Preset Chips -->
            <div class="space-y-2">
              <label class="text-xs font-medium text-slate-300">Orientation Presets</label>
              <div class="flex flex-wrap gap-1.5">
                <button 
                  v-for="preset in activeCam.orientation.presets" 
                  :key="preset"
                  @click="updateConfig({ orientation_mode: preset })"
                  class="px-3 py-1.5 rounded-lg text-xs font-medium transition border"
                  :class="activeCam.orientation.mode === preset 
                    ? 'bg-amber-600 text-white font-bold border-amber-500 shadow-md shadow-amber-600/30' 
                    : 'bg-slate-900 text-slate-300 border-slate-800 hover:border-slate-700'"
                >
                  {{ preset }}
                </button>
              </div>
            </div>

            <!-- Manual Toggle Switches -->
            <div class="grid grid-cols-2 gap-3 pt-2">
              <button 
                @click="updateConfig({ hflip: !activeCam.orientation.hflip })"
                class="p-3 rounded-xl border transition flex items-center justify-between"
                :class="activeCam.orientation.hflip ? 'bg-amber-500/20 border-amber-500/50 text-amber-300' : 'bg-slate-900/80 border-slate-800 text-slate-400 hover:text-slate-200'"
              >
                <div class="flex items-center gap-2">
                  <FlipHorizontal class="w-4 h-4" />
                  <span class="text-xs font-medium">Horizontal Flip</span>
                </div>
                <span class="text-[10px] font-mono px-1.5 py-0.5 rounded" :class="activeCam.orientation.hflip ? 'bg-amber-500/30 text-amber-200' : 'bg-slate-800 text-slate-500'">
                  {{ activeCam.orientation.hflip ? 'ON' : 'OFF' }}
                </span>
              </button>

              <button 
                @click="updateConfig({ vflip: !activeCam.orientation.vflip })"
                class="p-3 rounded-xl border transition flex items-center justify-between"
                :class="activeCam.orientation.vflip ? 'bg-amber-500/20 border-amber-500/50 text-amber-300' : 'bg-slate-900/80 border-slate-800 text-slate-400 hover:text-slate-200'"
              >
                <div class="flex items-center gap-2">
                  <FlipVertical class="w-4 h-4" />
                  <span class="text-xs font-medium">Vertical Flip (180°)</span>
                </div>
                <span class="text-[10px] font-mono px-1.5 py-0.5 rounded" :class="activeCam.orientation.vflip ? 'bg-amber-500/30 text-amber-200' : 'bg-slate-800 text-slate-500'">
                  {{ activeCam.orientation.vflip ? 'ON' : 'OFF' }}
                </span>
              </button>
            </div>
          </div>

          <!-- Digital Cropping & Zoom Card -->
          <div class="glass-panel rounded-2xl p-5 border border-slate-800 space-y-4">
            <div class="flex items-center justify-between border-b border-slate-800 pb-3">
              <div class="flex items-center gap-2">
                <Crop class="w-5 h-5 text-emerald-400" />
                <h3 class="text-base font-semibold text-white font-heading">Digital Cropping & ROI Zoom</h3>
              </div>
              <label class="relative inline-flex items-center cursor-pointer">
                <input 
                  type="checkbox" 
                  :checked="activeCam.crop.enabled" 
                  @change="updateConfig({ crop_enabled: !activeCam.crop.enabled })"
                  class="sr-only peer"
                >
                <div class="w-9 h-5 bg-slate-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-emerald-600"></div>
              </label>
            </div>

            <!-- Crop Presets -->
            <div class="space-y-2">
              <label class="text-xs font-medium text-slate-300">Crop & Zoom Presets</label>
              <div class="flex flex-wrap gap-1.5">
                <button 
                  v-for="preset in activeCam.crop.presets" 
                  :key="preset"
                  @click="updateConfig({ crop_preset: preset, crop_enabled: true })"
                  class="px-2.5 py-1 rounded-lg text-xs font-medium transition border"
                  :class="activeCam.crop.enabled && activeCam.crop.preset === preset 
                    ? 'bg-emerald-600 text-white font-bold border-emerald-500 shadow-md shadow-emerald-600/30' 
                    : 'bg-slate-900 text-slate-400 border-slate-800 hover:text-slate-200'"
                >
                  {{ preset }}
                </button>
              </div>
            </div>
          </div>

          <!-- Encoding & Stream Resolution Settings Card -->
          <div class="glass-panel rounded-2xl p-5 border border-slate-800 space-y-5">
            <div class="flex items-center justify-between border-b border-slate-800 pb-3">
              <div class="flex items-center gap-2">
                <Sliders class="w-5 h-5 text-cyan-400" />
                <h3 class="text-base font-semibold text-white font-heading">RPi5 Stream Parameters</h3>
              </div>
              <span class="text-xs text-slate-400 font-mono">Live API Updates</span>
            </div>

            <!-- 2.3.2 Resolution -->
            <div class="bg-slate-900/70 p-3.5 rounded-xl border border-slate-800/80 space-y-2.5">
              <div class="flex items-center justify-between">
                <span class="text-xs font-medium text-slate-200">Stream Resolution</span>
                <span class="text-xs text-cyan-400 font-mono font-bold">{{ activeCam.resolution.name }}</span>
              </div>

              <div class="flex flex-wrap gap-1.5 pt-1">
                <button 
                  v-for="res in activeCam.resolution.presets" 
                  :key="res"
                  @click="updateConfig({ resolution: res })"
                  class="px-3 py-1.5 rounded-lg text-xs font-mono transition border"
                  :class="activeCam.resolution.name === res 
                    ? 'bg-cyan-600 text-white font-bold border-cyan-500 shadow-sm' 
                    : 'bg-slate-800 text-slate-400 border-slate-700 hover:text-slate-200'"
                >
                  {{ res }}
                </button>
              </div>
            </div>

            <!-- 2.3.1 Framerate Cap -->
            <div class="bg-slate-900/70 p-3.5 rounded-xl border border-slate-800/80 space-y-2.5">
              <div class="flex items-center justify-between">
                <span class="text-xs font-medium text-slate-200">Framerate Cap (FPS)</span>
                <span class="text-xs text-emerald-400 font-mono font-bold">{{ activeCam.fps.value }} FPS</span>
              </div>

              <div class="flex flex-wrap gap-1.5 pt-1">
                <button 
                  v-for="rate in activeCam.fps.presets" 
                  :key="rate"
                  @click="updateConfig({ fps: rate })"
                  class="px-3 py-1.5 rounded-lg text-xs font-mono transition border"
                  :class="activeCam.fps.value === rate 
                    ? 'bg-cyan-600 text-white font-bold border-cyan-500 shadow-sm' 
                    : 'bg-slate-800 text-slate-400 border-slate-700 hover:text-slate-200'"
                >
                  {{ rate }}fps
                </button>
              </div>
            </div>

          </div>

        </div>

      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { 
  Camera, RefreshCw, Video, Globe, Film, Activity, Zap, Layers, 
  Cpu, Sliders, ShieldCheck, Settings, Copy, RotateCw, 
  FlipHorizontal, FlipVertical, Crop, Clock, Power
} from 'lucide-vue-next'

// Initial state optimized for RPi 5
const cameras = ref([
  {
    id: 0,
    name: "Camera 0 (CSI-0)",
    codec: "H.264",
    protocol: "RTSP",
    sync_telemetry: { timestamp: 0, timestamp_iso: "", frame_age_ms: 0 },
    orientation: { mode: "Normal (0°)", hflip: false, vflip: false, presets: ["Normal (0°)", "180° (Upside Down)", "H-Flip", "V-Flip"] },
    crop: { enabled: false, preset: "1.0x (Full)", zoom: 1.0, presets: ["1.0x (Full)", "1.2x Zoom", "1.5x Zoom", "2.0x Zoom", "Center 50%", "Top-Half", "Bottom-Half"] },
    fps: { enabled: true, value: 30, actual: 30, presets: [15, 24, 30, 60] },
    resolution: { enabled: true, name: "1080p", width: 1920, height: 1080, presets: ["1080p", "720p", "480p", "360p"] },
    quality: { enabled: true, name: "High", presets: ["Medium", "High", "Ultra"] },
    bitrate: { enabled: true, name: "2048kbps", presets: ["1024kbps", "2048kbps", "4096kbps", "8192kbps"] },
    aspect_ratio: { enabled: true, name: "16:9", presets: ["4:3", "16:9", "21:9"] },
    hardware: { model: "Sony IMX708 Wide-Angle", sensor_size: "1/2.8\"", shutter_speed: "1/1000s", aperture: "f/1.8", iso: 100, is_simulated: false },
    rtsp_url: "rtsp://10.0.0.5:8554/live/cam0"
  },
  {
    id: 1,
    name: "Camera 1 (CSI-1)",
    codec: "H.264",
    protocol: "RTSP",
    sync_telemetry: { timestamp: 0, timestamp_iso: "", frame_age_ms: 0 },
    orientation: { mode: "Normal (0°)", hflip: false, vflip: false, presets: ["Normal (0°)", "180° (Upside Down)", "H-Flip", "V-Flip"] },
    crop: { enabled: false, preset: "1.0x (Full)", zoom: 1.0, presets: ["1.0x (Full)", "1.2x Zoom", "1.5x Zoom", "2.0x Zoom", "Center 50%", "Top-Half", "Bottom-Half"] },
    fps: { enabled: true, value: 30, actual: 30, presets: [15, 24, 30, 60] },
    resolution: { enabled: true, name: "1080p", width: 1920, height: 1080, presets: ["1080p", "720p", "480p", "360p"] },
    quality: { enabled: true, name: "High", presets: ["Medium", "High", "Ultra"] },
    bitrate: { enabled: true, name: "2048kbps", presets: ["1024kbps", "2048kbps", "4096kbps", "8192kbps"] },
    aspect_ratio: { enabled: true, name: "16:9", presets: ["4:3", "16:9", "21:9"] },
    hardware: { model: "Sony IMX708 Wide-Angle", sensor_size: "1/2.8\"", shutter_speed: "1/1000s", aperture: "f/1.8", iso: 100, is_simulated: false },
    rtsp_url: "rtsp://10.0.0.5:8554/live/cam1"
  }
])

const activeCamId = ref(0)
const loading = ref(false)
const copied = ref(false)
const feedTimestamp = ref(Date.now())
let pollInterval = null

const activeCam = computed(() => {
  return cameras.value.find(c => c.id === activeCamId.value) || cameras.value[0]
})

const fetchCameras = async () => {
  loading.value = true
  try {
    const res = await fetch('/api/cameras')
    const data = await res.json()
    if (data.cameras && data.cameras.length > 0) {
      cameras.value = data.cameras
      if (!cameras.value.some(c => c.id === activeCamId.value)) {
        activeCamId.value = cameras.value[0].id
      }
    }
  } catch (err) {
    console.error('Error fetching cameras status:', err)
  } finally {
    loading.value = false
  }
}

const updateConfig = async (payload) => {
  if (!activeCam.value) return

  try {
    const res = await fetch(`/api/camera/${activeCam.value.id}/config`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    const data = await res.json()
    if (data.camera) {
      const idx = cameras.value.findIndex(c => c.id === activeCam.value.id)
      if (idx !== -1) {
        cameras.value[idx] = data.camera
      }
      feedTimestamp.value = Date.now()
    }
  } catch (err) {
    console.error('Error updating camera configuration:', err)
  }
}

const copyRtspUrl = (url) => {
  if (!url) return
  navigator.clipboard.writeText(url)
  copied.value = true
  setTimeout(() => { copied.value = false }, 2000)
}

onMounted(() => {
  fetchCameras()
  // Poll status metrics every 3 seconds
  pollInterval = setInterval(fetchCameras, 3000)
})

onUnmounted(() => {
  if (pollInterval) clearInterval(pollInterval)
})
</script>
