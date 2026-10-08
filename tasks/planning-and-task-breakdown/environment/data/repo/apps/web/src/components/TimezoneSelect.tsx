export function TimezoneSelect(props: { value: string; onChange(value: string): void; disabled?: boolean }) {
  return <select aria-label="Time zone" value={props.value} disabled={props.disabled} onChange={e => props.onChange(e.target.value)} />;
}
