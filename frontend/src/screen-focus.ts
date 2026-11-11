export function focusArea(node: HTMLElement | null) {
  const heading = node?.querySelector<HTMLElement>('h2');
  if (!heading) return;
  heading.setAttribute('tabindex', '-1');
  heading.focus({ preventScroll: true });
  heading.scrollIntoView?.({ block: 'start', behavior: 'instant' });
}
