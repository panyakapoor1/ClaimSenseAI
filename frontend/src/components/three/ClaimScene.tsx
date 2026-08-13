'use client';

import { useRef, useMemo, useState, useEffect, Suspense } from 'react';
import { Canvas, useFrame, type ThreeElements } from '@react-three/fiber';
import { RoundedBox, Float } from '@react-three/drei';
import * as THREE from 'three';

import { useResolvedTheme, type ResolvedTheme } from '@/lib/useTheme';

/**
 * The hero object: a bill, page by page, being read.
 *
 * A scan plane travels up the stack. As it crosses a page, that page's verdict
 * marker lights: approved, capped or rejected. It is the pipeline in miniature
 * rather than an abstract shape, which is the only reason it earns the bytes.
 */

const PAGE_COUNT = 7;
const PAGE_GAP = 0.3;
const STACK_HEIGHT = (PAGE_COUNT - 1) * PAGE_GAP;

/**
 * WebGL cannot read CSS variables, so the palette is duplicated here as literal
 * values and selected by the resolved theme. The dark set is re-picked rather
 * than darkened: the light spruce and oxblood disappear against a dark page.
 */
type Palette = {
  ink: string;
  paper: string;
  rule: string;
  policy: string;
  verified: string;
  capped: string;
  rejected: string;
  fill: string;
};

const PALETTE: Record<ResolvedTheme, Palette> = {
  light: {
    ink: '#15161a',
    paper: '#ffffff',
    rule: '#d1cec6',
    policy: '#eceae4',
    verified: '#14603f',
    capped: '#8a5a12',
    rejected: '#99271f',
    fill: '#c9d3e0',
  },
  dark: {
    ink: '#e8e8e6',
    paper: '#23252a',
    rule: '#4d5058',
    policy: '#2c2f35',
    verified: '#5fbe8f',
    capped: '#d7a24a',
    rejected: '#e4796f',
    fill: '#3b4250',
  },
};

/** Verdicts, in the order the demo bill happens to produce them. */
const VERDICT_KEYS = [
  'verified',
  'verified',
  'capped',
  'verified',
  'rejected',
  'verified',
  'capped',
] as const;

/** A page is the policy rather than the bill: tinted, and set slightly proud. */
const POLICY_INDEX = 3;

function TextRule({
  position,
  width,
  color,
}: {
  position: [number, number, number];
  width: number;
  color: string;
}) {
  return (
    <mesh position={position}>
      <boxGeometry args={[width, 0.012, 0.055]} />
      <meshBasicMaterial color={color} />
    </mesh>
  );
}

function Page({
  index,
  scanYRef,
  palette,
}: {
  index: number;
  scanYRef: React.RefObject<number>;
  palette: Palette;
}) {
  const marker = useRef<THREE.Mesh>(null);
  const y = index * PAGE_GAP - STACK_HEIGHT / 2;
  const isPolicy = index === POLICY_INDEX;

  // Each page is nudged off-axis so the stack reads as handled paper rather
  // than as a machined block.
  const { offsetX, offsetZ, tilt } = useMemo(
    () => ({
      offsetX: Math.sin(index * 2.7) * 0.06,
      offsetZ: Math.cos(index * 1.9) * 0.05,
      tilt: Math.sin(index * 1.3) * 0.02,
    }),
    [index],
  );

  // Rules stand in for line items. The policy page is denser, as a fifty-page
  // policy document is.
  const rules = useMemo(() => {
    const count = isPolicy ? 8 : 5;
    return Array.from({ length: count }, (_, i) => ({
      z: -0.75 + i * (1.5 / (count - 1)),
      width: 0.85 + ((i * 37) % 60) / 100,
    }));
  }, [isPolicy]);

  useFrame(() => {
    if (!marker.current) return;
    // Proximity of the scan plane to this page, 0..1.
    const distance = Math.abs((scanYRef.current ?? 0) - y);
    const heat = Math.max(0, 1 - distance / 0.42);
    const material = marker.current.material as THREE.MeshStandardMaterial;
    material.emissiveIntensity = 0.15 + heat * 2.4;
    marker.current.scale.setScalar(1 + heat * 0.5);
  });

  const verdict = palette[VERDICT_KEYS[index]];

  return (
    <group position={[offsetX, y, offsetZ]} rotation={[0, tilt, 0]}>
      <RoundedBox args={[2.1, 0.045, 2.9]} radius={0.02} smoothness={3} castShadow receiveShadow>
        <meshStandardMaterial
          color={isPolicy ? palette.policy : palette.paper}
          roughness={0.85}
          metalness={0}
        />
      </RoundedBox>

      {rules.map((rule, i) => (
        <TextRule
          key={i}
          position={[-0.25, 0.03, rule.z]}
          width={rule.width}
          color={palette.rule}
        />
      ))}

      {/* The verdict marker, in the margin where a stamp would go. */}
      <mesh ref={marker} position={[0.82, 0.04, -0.75]}>
        <boxGeometry args={[0.17, 0.02, 0.17]} />
        <meshStandardMaterial
          color={verdict}
          emissive={verdict}
          emissiveIntensity={0.15}
          roughness={0.5}
        />
      </mesh>
    </group>
  );
}

function ScanPlane({
  scanYRef,
  palette,
}: {
  scanYRef: React.RefObject<number>;
  palette: Palette;
}) {
  const group = useRef<THREE.Group>(null);

  useFrame(({ clock }) => {
    if (!group.current) return;
    // A slow sweep with a pause at each end, so the eye can follow it.
    const t = clock.getElapsedTime() * 0.42;
    const eased = Math.sin(t) * 0.5 + 0.5;
    const y = (eased - 0.5) * (STACK_HEIGHT + 0.9);
    group.current.position.y = y;
    scanYRef.current = y;
  });

  return (
    <group ref={group}>
      <mesh rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[3.1, 3.9]} />
        <meshBasicMaterial
          color={palette.ink}
          transparent
          opacity={0.07}
          side={THREE.DoubleSide}
          depthWrite={false}
        />
      </mesh>
      {/* The leading edge: a bright hairline is what makes it read as a scan. */}
      <mesh position={[0, 0, -1.95]}>
        <boxGeometry args={[3.1, 0.012, 0.012]} />
        <meshBasicMaterial color={palette.ink} />
      </mesh>
      <mesh position={[0, 0, 1.95]}>
        <boxGeometry args={[3.1, 0.012, 0.012]} />
        <meshBasicMaterial color={palette.ink} />
      </mesh>
    </group>
  );
}

function Stack({ palette }: { palette: Palette }) {
  const group = useRef<THREE.Group>(null);
  const scanYRef = useRef(0);

  useFrame(({ clock, pointer }, delta) => {
    if (!group.current) return;
    const t = clock.getElapsedTime();

    // Idle rotation, with the pointer adding a little parallax on top. Lerped so
    // a fast mouse does not snap the object around.
    const targetY = t * 0.12 + pointer.x * 0.35;
    const targetX = 0.34 + -pointer.y * 0.16;

    group.current.rotation.y = THREE.MathUtils.damp(
      group.current.rotation.y,
      targetY,
      4,
      delta,
    );
    group.current.rotation.x = THREE.MathUtils.damp(
      group.current.rotation.x,
      targetX,
      4,
      delta,
    );
  });

  return (
    <Float speed={1.1} rotationIntensity={0.12} floatIntensity={0.35}>
      <group ref={group}>
        {Array.from({ length: PAGE_COUNT }, (_, i) => (
          <Page key={i} index={i} scanYRef={scanYRef} palette={palette} />
        ))}
        <ScanPlane scanYRef={scanYRef} palette={palette} />
      </group>
    </Float>
  );
}

/**
 * True while the canvas is on screen and the tab is in front.
 *
 * Without this the render loop runs for the life of the page: still animating
 * after the reader has scrolled past the hero, and still animating in a
 * background tab. On a laptop that is a fan spinning up for nothing.
 */
function useIsVisible(ref: React.RefObject<HTMLElement | null>) {
  const [onScreen, setOnScreen] = useState(false);
  const [tabVisible, setTabVisible] = useState(true);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const observer = new IntersectionObserver(
      ([entry]) => setOnScreen(entry.isIntersecting),
      { rootMargin: '96px' },
    );
    observer.observe(el);

    const onVisibility = () => setTabVisible(!document.hidden);
    document.addEventListener('visibilitychange', onVisibility);

    return () => {
      observer.disconnect();
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, [ref]);

  return onScreen && tabVisible;
}

export default function ClaimScene(props: ThreeElements['group']) {
  const theme = useResolvedTheme();
  const dark = theme === 'dark';
  const palette = PALETTE[theme];

  const host = useRef<HTMLDivElement>(null);
  const active = useIsVisible(host);

  return (
    <div ref={host} className="h-full w-full">
    <Canvas
      dpr={[1, 1.8]}
      camera={{ position: [4.2, 2.4, 4.6], fov: 38 }}
      gl={{ antialias: true, alpha: true }}
      // 'never' halts the loop entirely; it resumes where it left off.
      frameloop={active ? 'always' : 'never'}
      style={{ pointerEvents: 'none' }}
    >
      <Suspense fallback={null}>
        {/* Lit a little harder in dark, where the pages have less of their own
            brightness to give back. */}
        <ambientLight intensity={dark ? 1.9 : 1.5} />
        <directionalLight position={[5, 8, 4]} intensity={dark ? 1.5 : 2.1} />
        <directionalLight position={[-4, 2, -3]} intensity={0.5} color={palette.fill} />
        <group {...props}>
          <Stack palette={palette} />
        </group>
      </Suspense>
    </Canvas>
    </div>
  );
}
