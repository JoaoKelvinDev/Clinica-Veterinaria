/**
 * Ref de callback para formulários e confirmações que abrem longe do botão clicado:
 * rola até o bloco e, num formulário, põe o foco no primeiro campo.
 * Como a função é estável, o React só a chama quando o bloco aparece; use `key`
 * para reabrir o mesmo bloco com outro conteúdo.
 */
export function reveal(node: HTMLElement | null) {
  if (!node) return;
  const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
  node.scrollIntoView?.({ behavior: reduce ? 'auto' : 'smooth', block: 'start' });
  if (node.tagName === 'FORM')
    node
      .querySelector<HTMLElement>('input:not([type=hidden]), select, textarea')
      ?.focus({ preventScroll: true });
}
