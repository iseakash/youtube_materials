import { useState, useEffect, useCallback } from 'react';

const API_BASE = 'http://localhost:5000/api/employees';

export default function Home() {
  const [employees, setEmployees] = useState([]);
  const [toast, setToast] = useState(null);

  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [dept, setDept] = useState('');
  const [position, setPosition] = useState('');
  const [salary, setSalary] = useState('');

  const [editId, setEditId] = useState(null);
  const [editName, setEditName] = useState('');
  const [editEmail, setEditEmail] = useState('');
  const [editDept, setEditDept] = useState('');
  const [editPosition, setEditPosition] = useState('');
  const [editSalary, setEditSalary] = useState('');
  const [showModal, setShowModal] = useState(false);

  const showToast = useCallback((message, type = 'success') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  }, []);

  const fetchEmployees = useCallback(async () => {
    try {
      const res = await fetch(API_BASE);
      if (!res.ok) throw new Error('Failed to fetch');
      const data = await res.json();
      setEmployees(data);
    } catch {
      showToast('Failed to load employees', 'error');
    }
  }, [showToast]);

  useEffect(() => {
    fetchEmployees();
  }, [fetchEmployees]);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') setShowModal(false);
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, []);

  const addEmployee = async () => {
    if (!name || !email) {
      showToast('Name and email are required', 'error');
      return;
    }
    try {
      const res = await fetch(API_BASE, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, email, department: dept, position, salary: salary || null }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error || 'Failed to add employee');
      }
      setName('');
      setEmail('');
      setDept('');
      setPosition('');
      setSalary('');
      showToast('Employee added successfully');
      fetchEmployees();
    } catch (err) {
      showToast(err.message, 'error');
    }
  };

  const openEditModal = async (id) => {
    try {
      const res = await fetch(`${API_BASE}/${id}`);
      if (!res.ok) throw new Error('Not found');
      const emp = await res.json();
      setEditId(emp.id);
      setEditName(emp.name);
      setEditEmail(emp.email);
      setEditDept(emp.department || '');
      setEditPosition(emp.position || '');
      setEditSalary(emp.salary || '');
      setShowModal(true);
    } catch {
      showToast('Failed to load employee details', 'error');
    }
  };

  const saveEdit = async () => {
    if (!editName || !editEmail) {
      showToast('Name and email are required', 'error');
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/${editId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: editName, email: editEmail, department: editDept, position: editPosition, salary: editSalary || null }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error || 'Failed to update');
      }
      setShowModal(false);
      showToast('Employee updated successfully');
      fetchEmployees();
    } catch (err) {
      showToast(err.message, 'error');
    }
  };

  const deleteEmployee = async (id) => {
    if (!confirm('Are you sure you want to delete this employee?')) return;
    try {
      const res = await fetch(`${API_BASE}/${id}`, { method: 'DELETE' });
      if (!res.ok) throw new Error('Failed to delete');
      showToast('Employee deleted successfully');
      fetchEmployees();
    } catch {
      showToast('Failed to delete employee', 'error');
    }
  };

  const formatSalary = (val) => {
    if (!val) return '0.00';
    return parseFloat(val).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  };

  return (
    <div className="container">
      <div className="header-info">
        <div>
          <h1>Employee Management System</h1>
          <p className="subtitle">Manage your team members with ease</p>
        </div>
        <span className="count">{employees.length} employee{employees.length !== 1 ? 's' : ''}</span>
      </div>

      <div className="form-section">
        <h2>Add New Employee</h2>
        <div className="form-grid">
          <div className="form-group">
            <label>Full Name *</label>
            <input type="text" placeholder="John Doe" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="form-group">
            <label>Email *</label>
            <input type="email" placeholder="john@company.com" value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div className="form-group">
            <label>Department</label>
            <input type="text" placeholder="Engineering" value={dept} onChange={(e) => setDept(e.target.value)} />
          </div>
          <div className="form-group">
            <label>Position</label>
            <input type="text" placeholder="Senior Developer" value={position} onChange={(e) => setPosition(e.target.value)} />
          </div>
          <div className="form-group">
            <label>Salary</label>
            <input type="number" placeholder="75000" step="0.01" value={salary} onChange={(e) => setSalary(e.target.value)} />
          </div>
          <button className="btn btn-primary btn-add" onClick={addEmployee}>+ Add Employee</button>
        </div>
      </div>

      <div className="table-section">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Name</th>
              <th>Email</th>
              <th>Department</th>
              <th>Position</th>
              <th>Salary</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {employees.length === 0 ? (
              <tr>
                <td colSpan={7}>
                  <div className="empty-state">
                    <h3>No employees yet</h3>
                    <p>Add your first employee using the form above.</p>
                  </div>
                </td>
              </tr>
            ) : (
              employees.map((emp) => (
                <tr key={emp.id}>
                  <td><span className="badge">#{emp.id}</span></td>
                  <td><strong>{emp.name}</strong></td>
                  <td>{emp.email}</td>
                  <td>{emp.department || '-'}</td>
                  <td>{emp.position || '-'}</td>
                  <td>${formatSalary(emp.salary)}</td>
                  <td>
                    <div className="action-btns">
                      <button className="btn btn-edit" onClick={() => openEditModal(emp.id)}>Edit</button>
                      <button className="btn btn-delete" onClick={() => deleteEmployee(emp.id)}>Delete</button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {showModal && (
        <div className="modal-overlay active" onClick={(e) => { if (e.target === e.currentTarget) setShowModal(false); }}>
          <div className="modal">
            <h2>Edit Employee</h2>
            <div className="form-group">
              <label>Full Name *</label>
              <input type="text" placeholder="John Doe" value={editName} onChange={(e) => setEditName(e.target.value)} />
            </div>
            <div className="form-group">
              <label>Email *</label>
              <input type="email" placeholder="john@company.com" value={editEmail} onChange={(e) => setEditEmail(e.target.value)} />
            </div>
            <div className="form-group">
              <label>Department</label>
              <input type="text" placeholder="Engineering" value={editDept} onChange={(e) => setEditDept(e.target.value)} />
            </div>
            <div className="form-group">
              <label>Position</label>
              <input type="text" placeholder="Senior Developer" value={editPosition} onChange={(e) => setEditPosition(e.target.value)} />
            </div>
            <div className="form-group">
              <label>Salary</label>
              <input type="number" placeholder="75000" step="0.01" value={editSalary} onChange={(e) => setEditSalary(e.target.value)} />
            </div>
            <div className="btn-row">
              <button className="btn btn-cancel" onClick={() => setShowModal(false)}>Cancel</button>
              <button className="btn btn-primary" onClick={saveEdit}>Save Changes</button>
            </div>
          </div>
        </div>
      )}

      {toast && <div className={`toast ${toast.type} show`}>{toast.message}</div>}

      <style jsx>{`
        * {
          margin: 0;
          padding: 0;
          box-sizing: border-box;
        }
        body {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          min-height: 100vh;
          padding: 20px;
        }
        .container {
          max-width: 1200px;
          margin: 0 auto;
          background: white;
          border-radius: 20px;
          padding: 30px;
          box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
        h1 {
          color: #2d3748;
          margin-bottom: 8px;
          font-size: 28px;
        }
        .subtitle {
          color: #718096;
          margin-bottom: 30px;
          font-size: 14px;
        }
        .form-section {
          background: #f7fafc;
          border-radius: 12px;
          padding: 25px;
          margin-bottom: 30px;
        }
        .form-section h2 {
          color: #2d3748;
          font-size: 18px;
          margin-bottom: 20px;
        }
        .form-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
          gap: 15px;
        }
        .form-group {
          display: flex;
          flex-direction: column;
        }
        .form-group label {
          font-size: 12px;
          font-weight: 600;
          color: #4a5568;
          margin-bottom: 5px;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }
        .form-group input {
          padding: 10px 14px;
          border: 2px solid #e2e8f0;
          border-radius: 8px;
          font-size: 14px;
          transition: border-color 0.2s;
          outline: none;
        }
        .form-group input:focus {
          border-color: #667eea;
        }
        .btn {
          padding: 10px 24px;
          border: none;
          border-radius: 8px;
          font-size: 14px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s;
          display: inline-flex;
          align-items: center;
          gap: 6px;
        }
        .btn-primary {
          background: #667eea;
          color: white;
        }
        .btn-primary:hover {
          background: #5a6fd6;
          transform: translateY(-1px);
        }
        .btn-edit {
          background: #48bb78;
          color: white;
        }
        .btn-edit:hover {
          background: #38a169;
        }
        .btn-delete {
          background: #f56565;
          color: white;
        }
        .btn-delete:hover {
          background: #e53e3e;
        }
        .btn-cancel {
          background: #a0aec0;
          color: white;
        }
        .btn-cancel:hover {
          background: #718096;
        }
        .btn-add {
          align-self: flex-end;
          height: 40px;
        }
        .table-section {
          overflow-x: auto;
        }
        table {
          width: 100%;
          border-collapse: collapse;
        }
        thead {
          background: #f7fafc;
        }
        th {
          text-align: left;
          padding: 14px 16px;
          font-size: 12px;
          font-weight: 600;
          color: #4a5568;
          text-transform: uppercase;
          letter-spacing: 0.5px;
          border-bottom: 2px solid #e2e8f0;
        }
        td {
          padding: 14px 16px;
          border-bottom: 1px solid #e2e8f0;
          color: #2d3748;
          font-size: 14px;
        }
        tr:hover {
          background: #f7fafc;
        }
        .action-btns {
          display: flex;
          gap: 8px;
        }
        .empty-state {
          text-align: center;
          padding: 60px 20px;
          color: #a0aec0;
        }
        .empty-state h3 {
          font-size: 18px;
          margin-bottom: 8px;
        }
        .toast {
          position: fixed;
          top: 20px;
          right: 20px;
          padding: 14px 24px;
          border-radius: 10px;
          color: white;
          font-weight: 500;
          font-size: 14px;
          box-shadow: 0 10px 30px rgba(0,0,0,0.2);
          transform: translateX(120%);
          transition: transform 0.3s ease;
          z-index: 1000;
        }
        .toast.show {
          transform: translateX(0);
        }
        .toast.success {
          background: #48bb78;
        }
        .toast.error {
          background: #f56565;
        }
        .modal-overlay {
          display: none;
          position: fixed;
          top: 0;
          left: 0;
          width: 100%;
          height: 100%;
          background: rgba(0,0,0,0.5);
          z-index: 999;
          align-items: center;
          justify-content: center;
        }
        .modal-overlay.active {
          display: flex;
        }
        .modal {
          background: white;
          border-radius: 16px;
          padding: 30px;
          width: 90%;
          max-width: 500px;
          box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
        .modal h2 {
          margin-bottom: 20px;
          color: #2d3748;
        }
        .modal .form-group {
          margin-bottom: 15px;
        }
        .modal .btn-row {
          display: flex;
          gap: 10px;
          margin-top: 20px;
          justify-content: flex-end;
        }
        .badge {
          display: inline-block;
          padding: 3px 10px;
          border-radius: 20px;
          font-size: 12px;
          font-weight: 500;
          background: #ebf4ff;
          color: #667eea;
        }
        @media (max-width: 768px) {
          .container { padding: 20px; }
          .form-grid { grid-template-columns: 1fr; }
          .action-btns { flex-direction: column; }
        }
        .header-info {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 30px;
          flex-wrap: wrap;
          gap: 10px;
        }
        .header-info .count {
          background: #ebf4ff;
          color: #667eea;
          padding: 6px 16px;
          border-radius: 20px;
          font-size: 14px;
          font-weight: 500;
        }
      `}</style>
    </div>
  );
}
