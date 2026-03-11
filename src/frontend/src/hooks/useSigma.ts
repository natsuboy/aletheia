import { useRef, useEffect, useCallback, useState } from 'react';
import Sigma from 'sigma';
import Graph from 'graphology';
import FA2Layout from 'graphology-layout-forceatlas2/worker';
import forceAtlas2 from 'graphology-layout-forceatlas2';
import noverlap from 'graphology-layout-noverlap';
import EdgeCurveProgram from '@sigma/edge-curve';
import type { SigmaNodeAttributes, SigmaEdgeAttributes } from '@/lib/graph-adapter';
import type { NodeAnimation } from '@/types/graph';
import type { EdgeType } from '@/lib/constants';

// ── Color helpers ──────────────────────────────────────────────

const hexToRgb = (hex: string): { r: number; g: number; b: number } => {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  return result
    ? { r: parseInt(result[1], 16), g: parseInt(result[2], 16), b: parseInt(result[3], 16) }
    : { r: 100, g: 100, b: 100 };
};

const rgbToHex = (r: number, g: number, b: number): string =>
  '#' + [r, g, b].map(x => Math.max(0, Math.min(255, Math.round(x))).toString(16).padStart(2, '0')).join('');

const dimColor = (hex: string, amount: number): string => {
  const rgb = hexToRgb(hex);
  const bg = { r: 18, g: 18, b: 28 };
  return rgbToHex(
    bg.r + (rgb.r - bg.r) * amount,
    bg.g + (rgb.g - bg.g) * amount,
    bg.b + (rgb.b - bg.b) * amount,
  );
};

const brightenColor = (hex: string, factor: number): string => {
  const rgb = hexToRgb(hex);
  return rgbToHex(
    rgb.r + (255 - rgb.r) * (factor - 1) / factor,
    rgb.g + (255 - rgb.g) * (factor - 1) / factor,
    rgb.b + (255 - rgb.b) * (factor - 1) / factor,
  );
};

// ── Types ──────────────────────────────────────────────────────

export interface UseSigmaOptions {
  onNodeClick?: (nodeId: string) => void;
  onNodeDoubleClick?: (nodeId: string) => void;
  onNodeHover?: (nodeId: string | null) => void;
  onStageClick?: () => void;
  highlightedNodeIds?: Set<string>;
  highlightedEdgePairs?: Set<string>;
  blastRadiusNodeIds?: Set<string>;
  animatedNodes?: Map<string, NodeAnimation>;
  visibleEdgeTypes?: EdgeType[];
}

export interface UseSigmaReturn {
  containerRef: React.RefObject<HTMLDivElement>;
  sigmaRef: React.RefObject<Sigma | null>;
  setGraph: (graph: Graph<SigmaNodeAttributes, SigmaEdgeAttributes>) => void;
  zoomIn: () => void;
  zoomOut: () => void;
  resetZoom: () => void;
  focusNode: (nodeId: string) => void;
  isLayoutRunning: boolean;
  startLayout: () => void;
  stopLayout: () => void;
  selectedNode: string | null;
  setSelectedNode: (nodeId: string | null) => void;
}

// ── ForceAtlas2 config ─────────────────────────────────────────

const NOVERLAP_SETTINGS = {
  maxIterations: 20,
  ratio: 2.5,
  margin: 50,
  expansion: 1.8,
  gridSize: 20,
};

const getFA2Settings = (nodeCount: number, edgeCount: number) => {
  const isSmall = nodeCount < 500;
  const isMedium = nodeCount >= 500 && nodeCount < 2000;
  const isLarge = nodeCount >= 2000 && nodeCount < 10000;

  return {
    gravity: isSmall ? 1.5 : isMedium ? 0.5 : isLarge ? 0.3 : 0.15,
    scalingRatio: isSmall ? 35 : isMedium ? 30 : isLarge ? 60 : 100,
    slowDown: isSmall ? 1 : isMedium ? 2 : isLarge ? 3 : 5,
    barnesHutOptimize: nodeCount > 200,
    barnesHutTheta: isLarge ? 0.8 : 0.6,
    strongGravityMode: isSmall ? true : false,
    outboundAttractionDistribution: false,
    linLogMode: nodeCount > 1000,
    adjustSizes: false,
    edgeWeightInfluence: nodeCount >= 10000 ? 0.5 : nodeCount >= 2000 ? 0.4 : 0.3,
  };
};

const getLayoutDuration = (nodeCount: number): number => {
  if (nodeCount > 10000) return 45000;
  if (nodeCount > 5000) return 35000;
  if (nodeCount > 2000) return 30000;
  if (nodeCount > 1000) return 30000;
  if (nodeCount > 500) return 25000;
  return 20000;
};

// ── Hook ───────────────────────────────────────────────────────

export const useSigma = (options: UseSigmaOptions = {}): UseSigmaReturn => {
  const containerRef = useRef<HTMLDivElement>(null!);
  const sigmaRef = useRef<Sigma | null>(null);
  const graphRef = useRef<Graph<SigmaNodeAttributes, SigmaEdgeAttributes> | null>(null);
  const layoutRef = useRef<FA2Layout | null>(null);
  const selectedNodeRef = useRef<string | null>(null);
  const highlightedRef = useRef<Set<string>>(new Set());
  const highlightedEdgePairsRef = useRef<Set<string>>(new Set());
  const blastRadiusRef = useRef<Set<string>>(new Set());
  const animatedNodesRef = useRef<Map<string, NodeAnimation>>(new Map());
  const visibleEdgeTypesRef = useRef<EdgeType[] | null>(null);
  const layoutTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const [isLayoutRunning, setIsLayoutRunning] = useState(false);
  const [selectedNode, setSelectedNodeState] = useState<string | null>(null);

  // Sync highlight/filter state to refs
  useEffect(() => {
    highlightedRef.current = options.highlightedNodeIds || new Set();
    highlightedEdgePairsRef.current = options.highlightedEdgePairs || new Set();
    blastRadiusRef.current = options.blastRadiusNodeIds || new Set();
    animatedNodesRef.current = options.animatedNodes || new Map();
    visibleEdgeTypesRef.current = options.visibleEdgeTypes || null;
    sigmaRef.current?.refresh();
  }, [options.highlightedNodeIds, options.highlightedEdgePairs, options.blastRadiusNodeIds, options.animatedNodes, options.visibleEdgeTypes]);

  // Animation loop for node effects
  useEffect(() => {
    if (!options.animatedNodes || options.animatedNodes.size === 0) {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
        animationFrameRef.current = null;
      }
      return;
    }
    const animate = () => {
      sigmaRef.current?.refresh();
      animationFrameRef.current = requestAnimationFrame(animate);
    };
    animate();
    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
        animationFrameRef.current = null;
      }
    };
  }, [options.animatedNodes]);

  const setSelectedNode = useCallback((nodeId: string | null) => {
    selectedNodeRef.current = nodeId;
    setSelectedNodeState(nodeId);
    const sigma = sigmaRef.current;
    if (!sigma) return;
    // Tiny camera nudge to force edge reducer refresh
    const camera = sigma.getCamera();
    camera.animate({ ratio: camera.ratio * 1.0001 }, { duration: 50 });
    sigma.refresh();
  }, []);

  // Initialize Sigma ONCE
  useEffect(() => {
    if (!containerRef.current) return;

    const graph = new Graph<SigmaNodeAttributes, SigmaEdgeAttributes>();
    graphRef.current = graph;

    const sigma = new Sigma(graph, containerRef.current, {
      allowInvalidContainer: true,
      renderLabels: true,
      labelFont: 'JetBrains Mono, monospace',
      labelSize: 14,
      labelWeight: '600',
      labelColor: { color: '#f5f5f7' },
      labelRenderedSizeThreshold: 0,
      labelDensity: 0.3,
      labelGridCellSize: 120,
      defaultNodeColor: '#6b7280',
      defaultEdgeColor: '#2a2a3a',
      defaultEdgeType: 'curved',
      edgeProgramClasses: { curved: EdgeCurveProgram },

      // Custom hover renderer — dark pill + node-color border + glow
      defaultDrawNodeHover: (context, data, settings) => {
        const label = data.label;
        if (!label) return;

        const size = settings.labelSize || 11;
        const font = settings.labelFont || 'JetBrains Mono, monospace';
        const weight = settings.labelWeight || '500';

        context.font = `${weight} ${size}px ${font}`;
        const textWidth = context.measureText(label).width;

        const nodeSize = data.size || 8;
        const x = data.x;
        const y = data.y - nodeSize - 10;
        const px = 8, py = 5;
        const h = size + py * 2;
        const w = textWidth + px * 2;

        context.fillStyle = '#12121c';
        context.beginPath();
        context.roundRect(x - w / 2, y - h / 2, w, h, 4);
        context.fill();

        context.strokeStyle = data.color || '#6366f1';
        context.lineWidth = 2;
        context.stroke();

        context.fillStyle = '#f5f5f7';
        context.textAlign = 'center';
        context.textBaseline = 'middle';
        context.fillText(label, x, y);

        // Glow ring
        context.beginPath();
        context.arc(data.x, data.y, nodeSize + 4, 0, Math.PI * 2);
        context.strokeStyle = data.color || '#6366f1';
        context.lineWidth = 2;
        context.globalAlpha = 0.5;
        context.stroke();
        context.globalAlpha = 1;
      },

      minCameraRatio: 0.002,
      maxCameraRatio: 50,
      hideEdgesOnMove: true,
      zIndex: true,

      // ── nodeReducer: highlights + animations + selection ──
      nodeReducer: (node, data) => {
        const res = { ...data };
        if (data.hidden) { res.hidden = true; return res; }

        const currentSelected = selectedNodeRef.current;
        const highlighted = highlightedRef.current;
        const blastRadius = blastRadiusRef.current;
        const animated = animatedNodesRef.current;
        const hasHighlights = highlighted.size > 0;
        const hasBlastRadius = blastRadius.size > 0;
        const isHighlighted = highlighted.has(node);
        const isBlastNode = blastRadius.has(node);

        // Animation effects (highest priority)
        const animation = animated.get(node);
        if (animation) {
          const elapsed = Date.now() - animation.startTime;
          const progress = Math.min(elapsed / animation.duration, 1);
          const phase = (Math.sin(progress * Math.PI * 4) + 1) / 2;
          if (animation.type === 'pulse') {
            res.size = (data.size || 8) * (1.8 + phase * 1.0);
            res.color = phase > 0.5 ? '#06b6d4' : brightenColor('#06b6d4', 1.3);
          } else if (animation.type === 'ripple') {
            res.size = (data.size || 8) * (1.3 + phase * 1.2);
            res.color = phase > 0.5 ? '#ef4444' : '#f87171';
          } else if (animation.type === 'glow') {
            res.size = (data.size || 8) * (1.4 + phase * 0.6);
            res.color = phase > 0.5 ? '#a855f7' : '#c084fc';
          }
          res.zIndex = 5; res.highlighted = true;
          return res;
        }

        // Blast radius (red highlighting)
        if (hasBlastRadius && !currentSelected) {
          if (isBlastNode) {
            res.color = '#ef4444'; res.size = (data.size || 8) * 2.0; res.zIndex = 3; res.highlighted = true;
          } else if (isHighlighted) {
            res.color = '#06b6d4'; res.size = (data.size || 8) * 1.8; res.zIndex = 2; res.highlighted = true;
          } else {
            res.color = dimColor(data.color, 0.5); res.size = (data.size || 8) * 0.7; res.zIndex = 0;
          }
          return res;
        }

        // Query/AI highlights (cyan)
        if (hasHighlights && !currentSelected) {
          if (isHighlighted) {
            res.color = '#06b6d4'; res.size = (data.size || 8) * 2.0; res.zIndex = 2; res.highlighted = true;
          } else {
            res.color = dimColor(data.color, 0.5); res.size = (data.size || 8) * 0.7; res.zIndex = 0;
          }
          return res;
        }

        // Selection highlight
        if (currentSelected) {
          const g = graphRef.current;
          if (g) {
            const isSelected = node === currentSelected;
            const isNeighbor = g.hasEdge(node, currentSelected) || g.hasEdge(currentSelected, node);
            if (isSelected) {
              res.size = (data.size || 8) * 2.0; res.zIndex = 2; res.highlighted = true;
            } else if (isNeighbor) {
              res.size = (data.size || 8) * 1.3; res.zIndex = 1;
            } else {
              res.color = dimColor(data.color, 0.5); res.size = (data.size || 8) * 0.7; res.zIndex = 0;
            }
          }
        }
        return res;
      },

      // ── edgeReducer: filter + highlights + selection ──
      edgeReducer: (edge, data) => {
        const res = { ...data };

        // Edge type visibility filter
        const visibleTypes = visibleEdgeTypesRef.current;
        if (visibleTypes && visibleTypes.length > 0 && data.relationType) {
          if (!visibleTypes.includes(data.relationType as EdgeType)) {
            res.hidden = true; return res;
          }
          res.hidden = false;
        }

        const currentSelected = selectedNodeRef.current;
        const highlighted = highlightedRef.current;
        const highlightedEdgePairs = highlightedEdgePairsRef.current;
        const blastRadius = blastRadiusRef.current;
        const hasHighlights = highlighted.size > 0 || blastRadius.size > 0 || highlightedEdgePairs.size > 0;
        const g = graphRef.current;

        if (hasHighlights && !currentSelected && g) {
          const [source, target] = g.extremities(edge);
          const edgeKey = `${source}->${target}`;
          const isPathEdge = highlightedEdgePairs.has(edgeKey);
          const isSourceActive = highlighted.has(source) || blastRadius.has(source);
          const isTargetActive = highlighted.has(target) || blastRadius.has(target);
          if (isPathEdge) {
            res.color = '#22d3ee';
            res.size = Math.max(3, (data.size || 1) * 5);
            res.zIndex = 3;
          } else if (isSourceActive && isTargetActive) {
            res.color = (blastRadius.has(source) && blastRadius.has(target)) ? '#ef4444' : '#06b6d4';
            res.size = Math.max(2, (data.size || 1) * 4); res.zIndex = 2;
          } else if (isSourceActive || isTargetActive) {
            res.color = dimColor('#06b6d4', 0.4); res.size = 1; res.zIndex = 1;
          } else {
            res.color = dimColor(data.color, 0.08); res.size = 0.2; res.zIndex = 0;
          }
          return res;
        }

        if (currentSelected && g) {
          const [source, target] = g.extremities(edge);
          const connected = source === currentSelected || target === currentSelected;
          if (connected) {
            res.color = brightenColor(data.color, 1.5);
            res.size = Math.max(3, (data.size || 1) * 5); res.zIndex = 2;
          } else {
            res.color = dimColor(data.color, 0.1); res.size = 0.3; res.zIndex = 0;
          }
        }
        return res;
      },
    });

    sigmaRef.current = sigma;

    // When container gets a valid size, refresh Sigma so it renders
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        if (width > 0 && height > 0) {
          sigma.refresh();
          break;
        }
      }
    });
    ro.observe(containerRef.current);

    sigma.on('clickNode', ({ node }) => {
      setSelectedNode(node);
      options.onNodeClick?.(node);
    });

    sigma.on('doubleClickNode', ({ node, event }) => {
      event.preventSigmaDefault();
      options.onNodeDoubleClick?.(node);
    });

    sigma.on('clickStage', () => {
      setSelectedNode(null);
      options.onStageClick?.();
    });

    sigma.on('enterNode', ({ node }) => {
      options.onNodeHover?.(node);
      if (containerRef.current) containerRef.current.style.cursor = 'pointer';
    });

    sigma.on('leaveNode', () => {
      options.onNodeHover?.(null);
      if (containerRef.current) containerRef.current.style.cursor = 'grab';
    });

    return () => {
      ro.disconnect();
      if (layoutTimeoutRef.current) clearTimeout(layoutTimeoutRef.current);
      layoutRef.current?.kill();
      sigma.kill();
      sigmaRef.current = null;
      graphRef.current = null;
    };
  }, []);

  // ── Layout runner ──
  const runLayout = useCallback((graph: Graph<SigmaNodeAttributes, SigmaEdgeAttributes>) => {
    const nodeCount = graph.order;
    if (nodeCount === 0) return;

    if (layoutRef.current) { layoutRef.current.kill(); layoutRef.current = null; }
    if (layoutTimeoutRef.current) { clearTimeout(layoutTimeoutRef.current); layoutTimeoutRef.current = null; }

    const inferredSettings = forceAtlas2.inferSettings(graph);
    const customSettings = getFA2Settings(nodeCount, graph.size);
    const settings = { ...inferredSettings, ...customSettings };

    const layout = new FA2Layout(graph, { settings });
    layoutRef.current = layout;
    layout.start();
    setIsLayoutRunning(true);

    layoutTimeoutRef.current = setTimeout(() => {
      if (layoutRef.current) {
        layoutRef.current.stop();
        layoutRef.current = null;
        noverlap.assign(graph, NOVERLAP_SETTINGS);
        sigmaRef.current?.refresh();
        setIsLayoutRunning(false);
      }
    }, getLayoutDuration(nodeCount));
  }, []);

  // ── setGraph: replace graph + run layout ──
  const setGraph = useCallback((newGraph: Graph<SigmaNodeAttributes, SigmaEdgeAttributes>) => {
    const sigma = sigmaRef.current;
    if (!sigma) return;

    if (layoutRef.current) { layoutRef.current.kill(); layoutRef.current = null; }
    if (layoutTimeoutRef.current) { clearTimeout(layoutTimeoutRef.current); layoutTimeoutRef.current = null; }

    graphRef.current = newGraph;
    sigma.setGraph(newGraph);
    setSelectedNode(null);
    runLayout(newGraph);
    sigma.getCamera().animatedReset({ duration: 500 });
  }, [runLayout, setSelectedNode]);

  // ── focusNode ──
  const focusNode = useCallback((nodeId: string) => {
    const sigma = sigmaRef.current;
    const graph = graphRef.current;
    if (!sigma || !graph || !graph.hasNode(nodeId)) return;

    const alreadySelected = selectedNodeRef.current === nodeId;
    selectedNodeRef.current = nodeId;
    setSelectedNodeState(nodeId);

    if (!alreadySelected) {
      const attrs = graph.getNodeAttributes(nodeId);
      sigma.getCamera().animate(
        { x: attrs.x, y: attrs.y, ratio: 0.15 },
        { duration: 400 },
      );
    }
    sigma.refresh();
  }, []);

  const zoomIn = useCallback(() => {
    sigmaRef.current?.getCamera().animatedZoom({ duration: 200 });
  }, []);

  const zoomOut = useCallback(() => {
    sigmaRef.current?.getCamera().animatedUnzoom({ duration: 200 });
  }, []);

  const resetZoom = useCallback(() => {
    sigmaRef.current?.getCamera().animatedReset({ duration: 300 });
    setSelectedNode(null);
  }, [setSelectedNode]);

  const startLayout = useCallback(() => {
    const graph = graphRef.current;
    if (!graph || graph.order === 0) return;
    runLayout(graph);
  }, [runLayout]);

  const stopLayout = useCallback(() => {
    if (layoutTimeoutRef.current) {
      clearTimeout(layoutTimeoutRef.current);
      layoutTimeoutRef.current = null;
    }
    if (layoutRef.current) {
      layoutRef.current.stop();
      layoutRef.current = null;
      const graph = graphRef.current;
      if (graph) {
        noverlap.assign(graph, NOVERLAP_SETTINGS);
        sigmaRef.current?.refresh();
      }
      setIsLayoutRunning(false);
    }
  }, []);

  return {
    containerRef,
    sigmaRef,
    setGraph,
    zoomIn,
    zoomOut,
    resetZoom,
    focusNode,
    isLayoutRunning,
    startLayout,
    stopLayout,
    selectedNode,
    setSelectedNode,
  };
};
