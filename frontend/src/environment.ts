export const isDemonstration = import.meta.env.VITE_DEMO_MODE === 'true';
export const environmentLabel = isDemonstration
  ? 'Demonstração — dados fictícios'
  : 'Desenvolvimento local';

// Reserva espaço para o multipart dentro do limite de upload da hospedagem.
export const maxDocumentMegabytes = isDemonstration ? 4 : 10;
