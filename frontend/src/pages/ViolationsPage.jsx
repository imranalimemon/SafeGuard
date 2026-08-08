import React, { useState, useEffect } from 'react';
import { getViolations, clearViolations } from '../api/client';

const ViolationsPage = () => {
  const [violations, setViolations] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [currentPage, setCurrentPage] = useState(1);
  const [filterType, setFilterType] = useState('All Types');
  const [filterTime, setFilterTime] = useState('All Time');
  const pageSize = 10;

  const fetchViolations = async () => {
    setIsLoading(true);
    try {
      const res = await getViolations({ limit: 200, offset: 0 });
      const data = Array.isArray(res.data) ? res.data : [];
      setViolations(data);
    } catch (error) {
      console.error("Error fetching violations", error);
      setViolations([]);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchViolations();
  }, []);

  // Filter violations
  const filteredViolations = violations.filter(v => {
    // Type filter
    if (filterType === 'No Helmet' && !(v.missing_ppe || '').includes('Helmet')) return false;
    if (filterType === 'No Vest' && !(v.missing_ppe || '').includes('Safety Vest')) return false;
    
    // Time filter
    if (filterTime !== 'All Time') {
      const vDate = new Date(v.timestamp);
      const now = new Date();
      if (filterTime === 'Last 24 Hours') {
        const dayAgo = new Date(now.getTime() - 24 * 60 * 60 * 1000);
        if (vDate < dayAgo) return false;
      } else if (filterTime === 'Last 7 Days') {
        const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
        if (vDate < weekAgo) return false;
      }
    }
    return true;
  });

  // Pagination
  const totalPages = Math.max(1, Math.ceil(filteredViolations.length / pageSize));
  const paginatedViolations = filteredViolations.slice(
    (currentPage - 1) * pageSize,
    currentPage * pageSize
  );

  // Reset to page 1 when filters change
  useEffect(() => {
    setCurrentPage(1);
  }, [filterType, filterTime]);

  const handleClearAll = async () => {
    if (window.confirm("Are you sure you want to clear all violations? This cannot be undone.")) {
      try {
        await clearViolations();
        setViolations([]);
        setCurrentPage(1);
      } catch (error) {
        console.error("Error clearing violations", error);
      }
    }
  };

  const handleExportCSV = () => {
    if (filteredViolations.length === 0) return;
    const headers = ['ID', 'Timestamp', 'Type', 'Persons', 'Confidence', 'Missing PPE'];
    const rows = filteredViolations.map(v => [
      v.id,
      v.timestamp,
      v.violation_type || '',
      v.person_count || 0,
      v.confidence ? (v.confidence * 100).toFixed(1) + '%' : '',
      v.missing_ppe || ''
    ]);
    const csvContent = "data:text/csv;charset=utf-8,"
      + [headers.join(','), ...rows.map(e => e.join(','))].join('\n');
    const link = document.createElement("a");
    link.setAttribute("href", encodeURI(csvContent));
    link.setAttribute("download", `safeguard_violations_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="h-full flex flex-col">
      {/* Page Header Actions */}
      <div className="flex justify-between items-end mb-8">
        <div>
          <h3 className="font-headline-lg text-sg-on-surface mb-1">{filteredViolations.length} Violations</h3>
          <p className="font-body-md text-sg-on-surface-variant">{filterTime} &bull; {filterType}</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleClearAll}
            className="flex items-center gap-2 px-4 py-2 bg-transparent border border-sg-outline-variant text-sg-on-surface rounded hover:bg-sg-surface-container-high hover:border-sg-outline transition-all duration-200"
          >
            <span className="material-symbols-outlined text-sm">delete</span>
            <span className="font-body-md font-medium">Clear All</span>
          </button>
          <button
            onClick={handleExportCSV}
            className="flex items-center gap-2 px-4 py-2 bg-sg-primary text-sg-on-primary font-medium rounded hover:bg-sg-primary-fixed transition-all duration-200 shadow-[0_0_15px_rgba(255,182,147,0.15)] hover:shadow-[0_0_20px_rgba(255,182,147,0.25)]"
          >
            <span className="material-symbols-outlined text-sm">download</span>
            <span className="font-body-md font-bold">Export CSV</span>
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-2 mb-8">
        <div className="relative">
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            className="appearance-none bg-sg-surface-container border border-sg-outline-variant text-sg-on-surface font-body-md rounded-lg pl-4 pr-10 py-2 focus:outline-none focus:border-sg-primary focus:ring-1 focus:ring-sg-primary transition-colors cursor-pointer w-40"
          >
            <option>All Types</option>
            <option>No Helmet</option>
            <option>No Vest</option>
          </select>
          <span className="material-symbols-outlined absolute right-3 top-1/2 -translate-y-1/2 text-sg-on-surface-variant pointer-events-none text-sm">expand_more</span>
        </div>
        <div className="relative">
          <select
            value={filterTime}
            onChange={(e) => setFilterTime(e.target.value)}
            className="appearance-none bg-sg-surface-container border border-sg-outline-variant text-sg-on-surface font-body-md rounded-lg pl-4 pr-10 py-2 focus:outline-none focus:border-sg-primary focus:ring-1 focus:ring-sg-primary transition-colors cursor-pointer w-40"
          >
            <option>All Time</option>
            <option>Last 24 Hours</option>
            <option>Last 7 Days</option>
          </select>
          <span className="material-symbols-outlined absolute right-3 top-1/2 -translate-y-1/2 text-sg-on-surface-variant pointer-events-none text-sm">expand_more</span>
        </div>
      </div>

      {/* Data Table Container */}
      <div className="bg-sg-surface-container border border-sg-outline-variant rounded-xl overflow-hidden flex flex-col shadow-lg shadow-black/20 flex-1">
        {/* Table Header */}
        <div className="grid grid-cols-12 gap-4 px-6 py-4 border-b border-sg-outline-variant bg-sg-surface-container-low">
          <div className="col-span-1 font-label-caps text-sg-on-surface-variant">Image</div>
          <div className="col-span-3 font-label-caps text-sg-on-surface-variant">Timestamp</div>
          <div className="col-span-3 font-label-caps text-sg-on-surface-variant">Type</div>
          <div className="col-span-1 font-label-caps text-sg-on-surface-variant text-right">Persons</div>
          <div className="col-span-2 font-label-caps text-sg-on-surface-variant text-right">Confidence</div>
          <div className="col-span-2 font-label-caps text-sg-on-surface-variant">Missing PPE</div>
        </div>

        {/* Table Body */}
        <div className="flex-1 overflow-y-auto">
          {isLoading ? (
            <div className="flex items-center justify-center py-16 gap-3">
              <div className="w-5 h-5 border-2 border-sg-primary/30 border-t-sg-primary rounded-full animate-spin"></div>
              <span className="font-body-md text-sg-on-surface-variant">Loading violations...</span>
            </div>
          ) : paginatedViolations.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16">
              <span className="material-symbols-outlined text-4xl text-sg-surface-bright mb-3">shield</span>
              <p className="font-body-md text-sg-on-surface-variant">
                {violations.length === 0 ? 'No violations recorded yet.' : 'No violations match your filters.'}
              </p>
            </div>
          ) : (
            paginatedViolations.map((v, idx) => (
              <div
                key={v.id}
                className="grid grid-cols-12 gap-4 px-6 py-3 items-center border-b border-sg-outline-variant/50 hover:bg-sg-surface-variant transition-colors duration-150 group border-l-2 border-l-transparent hover:border-l-sg-primary animate-stagger-1"
                style={{ animationDelay: `${(idx + 1) * 50}ms` }}
              >
                <div className="col-span-1">
                  <div className="w-12 h-12 rounded border border-sg-outline-variant/50 overflow-hidden relative">
                    {v.screenshot_path ? (
                      <img src={v.screenshot_path} alt="Violation" className="w-full h-full object-cover" />
                    ) : (
                      <div className="w-full h-full bg-sg-surface-container-lowest flex items-center justify-center">
                        <span className="material-symbols-outlined text-sg-surface-bright text-sm">image</span>
                      </div>
                    )}
                    <div className="absolute inset-0 border border-sg-error/50 pointer-events-none mix-blend-screen"></div>
                  </div>
                </div>
                <div className="col-span-3 font-data-mono text-sg-on-surface">
                  {new Date(v.timestamp).toLocaleString()}
                </div>
                <div className="col-span-3">
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-sg-error-container/20 text-sg-error border border-sg-error/30">
                    {v.violation_type || 'Violation'}
                  </span>
                </div>
                <div className="col-span-1 font-data-mono text-sg-on-surface text-right">
                  {v.person_count || '-'}
                </div>
                <div className="col-span-2 font-data-mono text-sg-on-surface text-right font-bold">
                  {v.confidence ? Math.round(v.confidence * 100) + '%' : '-'}
                </div>
                <div className="col-span-2 font-body-md text-sg-on-surface-variant">
                  {v.missing_ppe || 'None'}
                </div>
              </div>
            ))
          )}
        </div>

        {/* Pagination Footer */}
        <div className="px-6 py-4 border-t border-sg-outline-variant bg-sg-surface-container-low flex items-center justify-between">
          <span className="font-body-md text-sg-on-surface-variant">
            Showing {filteredViolations.length === 0 ? 0 : (currentPage - 1) * pageSize + 1}
            -{Math.min(currentPage * pageSize, filteredViolations.length)} of {filteredViolations.length}
          </span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
              disabled={currentPage === 1}
              className="flex items-center px-3 py-1 rounded bg-sg-surface border border-sg-outline-variant text-sg-on-surface-variant hover:text-sg-on-surface hover:bg-sg-surface-container-high transition-colors text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <span className="material-symbols-outlined text-[16px] mr-1">chevron_left</span> Prev
            </button>
            {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => {
              let page;
              if (totalPages <= 5) {
                page = i + 1;
              } else if (currentPage <= 3) {
                page = i + 1;
              } else if (currentPage >= totalPages - 2) {
                page = totalPages - 4 + i;
              } else {
                page = currentPage - 2 + i;
              }
              return (
                <button
                  key={page}
                  onClick={() => setCurrentPage(page)}
                  className={`px-3 py-1 rounded text-sm font-bold transition-colors ${
                    currentPage === page
                      ? 'bg-sg-primary text-sg-on-primary'
                      : 'bg-sg-surface border border-sg-outline-variant text-sg-on-surface-variant hover:text-sg-on-surface hover:bg-sg-surface-container-high'
                  }`}
                >
                  {page}
                </button>
              );
            })}
            <button
              onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages}
              className="flex items-center px-3 py-1 rounded bg-sg-surface border border-sg-outline-variant text-sg-on-surface-variant hover:text-sg-on-surface hover:bg-sg-surface-container-high transition-colors text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Next <span className="material-symbols-outlined text-[16px] ml-1">chevron_right</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ViolationsPage;
