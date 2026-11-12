import React, { useState, useEffect } from 'react';
import { FilterCondition, FilterGroup, useFilterState } from '@operation-room/context/FilterStateProvider';
import { Plus, X, Filter } from 'lucide-react';

interface AdvancedFilterBuilderProps {
  moduleName: string;
  isGlobal?: boolean;
}

export const AdvancedFilterBuilder: React.FC<AdvancedFilterBuilderProps> = ({ moduleName, isGlobal = false }) => {
  const { state, setGlobalFilters, setLocalFilters } = useFilterState();
  const filterGroup = isGlobal ? state.globalFilters : (state.localFilters[moduleName] || { logic: 'AND', conditions: [] });

  const updateFilters = (newGroup: FilterGroup) => {
    if (isGlobal) {
      setGlobalFilters(newGroup);
    } else {
      setLocalFilters(moduleName, newGroup);
    }
  };

  const addCondition = () => {
    const newCondition: FilterCondition = { field: 'actor', op: 'eq', value: '' };
    updateFilters({ ...filterGroup, conditions: [...filterGroup.conditions, newCondition] });
  };

  const removeCondition = (index: number) => {
    const newConditions = [...filterGroup.conditions];
    newConditions.splice(index, 1);
    updateFilters({ ...filterGroup, conditions: newConditions });
  };

  const updateCondition = (index: number, key: keyof FilterCondition, value: any) => {
    const newConditions = [...filterGroup.conditions];
    const cond = newConditions[index] as FilterCondition;
    newConditions[index] = { ...cond, [key]: value };
    updateFilters({ ...filterGroup, conditions: newConditions });
  };

  const setLogic = (logic: 'AND' | 'OR' | 'NOT') => {
    updateFilters({ ...filterGroup, logic });
  };

  return (
    <div className="bg-slate-900 border border-slate-700/50 rounded-md p-3 mb-4 mt-2">
      <div className="flex items-center justify-between mb-3 border-b border-slate-700/50 pb-2">
        <h4 className="text-sm font-semibold text-slate-300 flex items-center gap-2">
          <Filter size={14} className="text-blue-400" />
          <span className="capitalize">{isGlobal ? 'Global Filters' : `${moduleName} Filters`}</span>
        </h4>
        <div className="flex bg-slate-800 rounded-md border border-slate-700/30 p-1">
          {['AND', 'OR', 'NOT'].map(l => (
            <button 
              key={l}
              onClick={() => setLogic(l as any)}
              className={`text-xs px-2 py-1 rounded transition-colors ${filterGroup.logic === l ? 'bg-blue-600/30 text-blue-400 font-medium' : 'text-slate-400 hover:text-slate-200'} `}
            >
              {l}
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-2">
        {filterGroup.conditions.map((item, idx) => {
          if ('field' in item) {
            return (
              <div key={idx} className="flex gap-2 items-center">
                <input 
                  type="text" 
                  value={item.field}
                  onChange={e => updateCondition(idx, 'field', e.target.value)}
                  placeholder="field"
                  className="bg-slate-800 border border-slate-700 rounded px-2 py-1 text-xs text-slate-200 w-1/3 outline-none focus:border-blue-500/50"
                />
                <select 
                  value={item.op}
                  onChange={e => updateCondition(idx, 'op', e.target.value)}
                  className="bg-slate-800 border border-slate-700 rounded px-2 py-1 text-xs text-slate-200 w-1/4 outline-none focus:border-blue-500/50"
                >
                  <option value="eq">=</option>
                  <option value="neq">!=</option>
                  <option value="gt">&gt;</option>
                  <option value="gte">&gt;=</option>
                  <option value="lt">&lt;</option>
                  <option value="lte">&lt;=</option>
                  <option value="contains">contains</option>
                  <option value="in">in</option>
                </select>
                <input 
                  type="text" 
                  value={item.value || ''}
                  onChange={e => updateCondition(idx, 'value', e.target.value)}
                  placeholder="value"
                  className="bg-slate-800 border border-slate-700 rounded px-2 py-1 text-xs text-slate-200 flex-1 outline-none focus:border-blue-500/50"
                />
                <button onClick={() => removeCondition(idx)} className="text-slate-400 hover:text-red-400 transition-colors p-1">
                  <X size={14} />
                </button>
              </div>
            );
          }
          return null;
        })}
        {filterGroup.conditions.length === 0 && (
          <div className="text-xs text-slate-500 italic py-2">No filters applied.</div>
        )}
      </div>

      <button onClick={addCondition} className="mt-3 flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 transition-colors">
        <Plus size={14} /> Add Condition
      </button>
    </div>
  );
};
