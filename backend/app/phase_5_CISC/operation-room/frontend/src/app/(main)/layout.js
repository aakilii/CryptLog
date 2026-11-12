
import AppChrome from '@operation-room/components/AppChrome';
import { FilterStateProvider } from '@operation-room/context/FilterStateProvider';

export default function MainLayout({ children }) {
  return (
    <FilterStateProvider>
      <AppChrome>{children}</AppChrome>
    </FilterStateProvider>
  );
}
