export function SettingsPanel(props: { title: string; description: string; children: any }) {
  return <section aria-labelledby={`${props.title}-heading`}><h2 id={`${props.title}-heading`}>{props.title}</h2><p>{props.description}</p>{props.children}</section>;
}
