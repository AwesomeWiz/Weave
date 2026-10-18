import { useEffect, useRef } from 'react';
import { BaseEdge, EdgeLabelRenderer, getBezierPath } from '@xyflow/react';
import type { Edge, EdgeProps } from '@xyflow/react';
import type { TraceClock } from '../traceClock';
import { useTraceClockState } from '../useTracePlayback';

export type TraceEdgeData = { clock?: TraceClock; active?: boolean; reverse?: boolean; [key: string]: unknown };
type Props = EdgeProps<Edge<TraceEdgeData>>;

function Motion({ path, clock, reverse, edgeId }: { path: string; clock: TraceClock; reverse: boolean; edgeId: string }) {
  const track = useRef<SVGPathElement>(null);
  const dot = useRef<SVGCircleElement>(null);
  useEffect(() => {
    const curve = track.current, point = dot.current;
    if (!curve || !point) return;
    const length = curve.getTotalLength();
    return clock.subscribeFrame(progress => {
      const location = curve.getPointAtLength((reverse ? 1 - progress : progress) * length);
      point.setAttribute('cx', String(location.x)); point.setAttribute('cy', String(location.y));
      point.dataset.progress = progress.toFixed(5);
      curve.setAttribute('stroke-dashoffset', String((reverse ? -1 : 1) * (1 - progress)));
    });
  }, [path, clock, reverse]);
  return <g className="trace-edge-motion" aria-hidden="true" data-edge-id={edgeId} data-direction={reverse ? 'reverse' : 'forward'}>
    <path ref={track} d={path} fill="none" className="trace-edge-light" pathLength={1} strokeDasharray="1 1" />
    <circle ref={dot} className="trace-edge-dot" r={4.5} />
  </g>;
}

function Geometry({ props, path, labelX, labelY, detour = false }: { props: Props; path: string; labelX: number; labelY: number; detour?: boolean }) {
  const { id, data, markerEnd, label, style } = props;
  const state = useTraceClockState(data?.clock);
  return <>
    <BaseEdge id={id} path={path} markerEnd={markerEnd} style={style} {...(!detour ? { label, labelX, labelY,
      labelStyle: props.labelStyle, labelBgStyle: props.labelBgStyle, labelBgPadding: props.labelBgPadding, labelBgBorderRadius: props.labelBgBorderRadius } : {})} />
    {detour && <EdgeLabelRenderer><span className="graph-edge-label" style={{ transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)` }}>{label}</span></EdgeLabelRenderer>}
    {data?.active && data.clock && !state.reduced && <Motion path={path} clock={data.clock} reverse={!!data.reverse} edgeId={id} />}
  </>;
}

export function TraceEdge(props: Props) {
  const [path, labelX, labelY] = getBezierPath(props);
  return <Geometry props={props} path={path} labelX={labelX} labelY={labelY} />;
}

export function TraceDetourEdge(props: Props) {
  // The same geometry as the existing long same-column edge, including its label.
  const { sourceX, sourceY, targetX, targetY } = props;
  const path = `M ${sourceX} ${sourceY} C ${sourceX + 125} ${sourceY}, ${targetX + 125} ${targetY}, ${targetX} ${targetY}`;
  const t = 0.36;
  const labelX = sourceX + 3 * 125 * t * (1 - t);
  const labelY = sourceY + (targetY - sourceY) * (3 * t * t - 2 * t * t * t);
  return <Geometry props={props} path={path} labelX={labelX} labelY={labelY} detour />;
}
