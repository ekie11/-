export function ErrorBanner({ message }: { message: string }) {
  return (
    <div role="alert" className="border border-red-700 bg-red-50 text-red-700 rounded-md px-3 py-2 text-sm">
      {message}
    </div>
  );
}
