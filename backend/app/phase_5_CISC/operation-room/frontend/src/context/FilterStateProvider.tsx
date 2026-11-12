'use client';
import React, { createContext, useContext, useState, useMemo, useCallback } from 'react';

// Advanced Filter State Management

export type FilterCondition = {
  field: string;
  op: 'eq' | 'neq' | 'gt' | 'gte' | 'lt' | 'lte' | 'contains' | 'in' | 'between';
  value: any;
};

export type FilterGroup = {
  logic: 'AND' | 'OR' | 'NOT';
  conditions: (FilterCondition | FilterGroup)[];
};

type FilterState = {
  globalFilters: FilterGroup;
  localFilters: Record<string, FilterGroup>; // e.g. { timeline: {...}, network: {...} }
};

type FilterContextType = {
  state: FilterState;
  setGlobalFilters: (filters: FilterGroup) => void;
  setLocalFilters: (moduleName: string, filters: FilterGroup) => void;
  getMergedFilters: (moduleName: string) => FilterGroup;
  clearFilters: (moduleName?: string) => void;
};

const defaultContext: FilterContextType = {
  state: {
    globalFilters: { logic: 'AND', conditions: [] },
    localFilters: {}
  },
  setGlobalFilters: () => {},
  setLocalFilters: () => {},
  getMergedFilters: () => ({ logic: 'AND', conditions: [] }),
  clearFilters: () => {}
};

const FilterContext = createContext<FilterContextType>(defaultContext);

export const useFilterState = () => useContext(FilterContext);

export const FilterStateProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [state, setState] = useState<FilterState>({
    globalFilters: { logic: 'AND', conditions: [] },
    localFilters: {}
  });

  const setGlobalFilters = useCallback((filters: FilterGroup) => {
    setState(prev => ({ ...prev, globalFilters: filters }));
  }, []);

  const setLocalFilters = useCallback((moduleName: string, filters: FilterGroup) => {
    setState(prev => ({
      ...prev,
      localFilters: { ...prev.localFilters, [moduleName]: filters }
    }));
  }, []);

  const clearFilters = useCallback((moduleName?: string) => {
    if (moduleName) {
      setState(prev => {
        const newLocal = { ...prev.localFilters };
        delete newLocal[moduleName];
        return { ...prev, localFilters: newLocal };
      });
    } else {
      // Clear all
      setState({
        globalFilters: { logic: 'AND', conditions: [] },
        localFilters: {}
      });
    }
  }, []);

  const getMergedFilters = useCallback((moduleName: string): FilterGroup => {
    const globalGroup = state.globalFilters;
    const localGroup = state.localFilters[moduleName];

    if (!localGroup || localGroup.conditions.length === 0) {
      return globalGroup;
    }
    if (globalGroup.conditions.length === 0) {
      return localGroup;
    }

    // Merge both using an AND group at the top level
    return {
      logic: 'AND',
      conditions: [globalGroup, localGroup]
    };
  }, [state.globalFilters, state.localFilters]);

  const value = useMemo(() => ({
    state,
    setGlobalFilters,
    setLocalFilters,
    getMergedFilters,
    clearFilters
  }), [state, setGlobalFilters, setLocalFilters, getMergedFilters, clearFilters]);

  return (
    <FilterContext.Provider value={value}>
      {children}
    </FilterContext.Provider>
  );
};
