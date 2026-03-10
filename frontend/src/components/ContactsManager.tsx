import React, { useCallback, useEffect, useState } from "react";
import {
  UserCircleIcon,
  PlusIcon,
  XMarkIcon,
  EnvelopeIcon,
  PhoneIcon,
  TrashIcon,
} from "@heroicons/react/24/outline";
import { getContacts, createContact, deleteContact } from "@/services/api";
import type { ContactItem } from "@/types";

export default function ContactsManager() {
  const [contacts, setContacts] = useState<ContactItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [relationship, setRelationship] = useState("");
  const [notes, setNotes] = useState("");
  const [searchQuery, setSearchQuery] = useState("");

  const loadContacts = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getContacts();
      setContacts(data);
    } catch {
      // Data unavailable
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadContacts();
  }, [loadContacts]);

  const handleCreate = async () => {
    if (!name.trim()) return;
    try {
      await createContact({ name, email, phone, relationship, notes });
      setName("");
      setEmail("");
      setPhone("");
      setRelationship("");
      setNotes("");
      setShowForm(false);
      loadContacts();
    } catch {
      // Failed
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteContact(id);
      loadContacts();
    } catch {
      // Failed
    }
  };

  const filtered = searchQuery
    ? contacts.filter(
        (c) =>
          c.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
          (c.email && c.email.toLowerCase().includes(searchQuery.toLowerCase())) ||
          (c.phone && c.phone.includes(searchQuery)),
      )
    : contacts;

  return (
    <div className="flex-1 flex flex-col h-full bg-transparent p-6 md:p-10 lg:p-14 overflow-hidden relative">
      {/* Header */}
      <div className="flex items-center justify-between mb-8 z-10">
        <div>
          <h2 className="text-3xl font-light text-jarvis-text tracking-wide drop-shadow-sm">
            Contacts
          </h2>
          <p className="text-jarvis-muted mt-2 text-[14px] font-light tracking-wide">
            {contacts.length} contacts saved
          </p>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="flex items-center gap-2 px-5 py-2.5 rounded-full bg-jarvis-glass-bg border border-jarvis-accent-cyan text-jarvis-accent-cyan text-[13px] font-medium transition-all duration-500 shadow-halo-cyan hover:bg-jarvis-accent-cyan hover:text-white"
        >
          <PlusIcon className="w-4 h-4" />
          Add Contact
        </button>
      </div>

      {/* Search */}
      <div className="relative mb-6 z-10">
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search contacts..."
          className="w-full bg-jarvis-panel border border-jarvis-border rounded-full py-3 pl-5 pr-4 text-jarvis-text placeholder:text-jarvis-muted text-sm focus:outline-none focus:ring-1 focus:ring-jarvis-accent-primary transition-shadow"
        />
      </div>

      {/* Create Form */}
      {showForm && (
        <div className="mb-6 p-5 rounded-[8px] bg-jarvis-surface border border-jarvis-border shadow-sm z-10">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-jarvis-text font-medium">Add Contact</h3>
            <button
              onClick={() => setShowForm(false)}
              className="text-jarvis-muted hover:text-jarvis-text"
            >
              <XMarkIcon className="w-5 h-5" />
            </button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Name *"
              className="bg-jarvis-panel border border-jarvis-border rounded-xl px-4 py-2.5 text-jarvis-text placeholder:text-jarvis-muted text-sm focus:outline-none focus:ring-1 focus:ring-jarvis-accent-primary"
            />
            <input
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Email"
              type="email"
              className="bg-jarvis-panel border border-jarvis-border rounded-xl px-4 py-2.5 text-jarvis-text placeholder:text-jarvis-muted text-sm focus:outline-none focus:ring-1 focus:ring-jarvis-accent-primary"
            />
            <input
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="Phone (e.g. +91XXXXXXXXXX)"
              className="bg-jarvis-panel border border-jarvis-border rounded-xl px-4 py-2.5 text-jarvis-text placeholder:text-jarvis-muted text-sm focus:outline-none focus:ring-1 focus:ring-jarvis-accent-primary"
            />
            <input
              value={relationship}
              onChange={(e) => setRelationship(e.target.value)}
              placeholder="Relationship (e.g. professor, friend)"
              className="bg-jarvis-panel border border-jarvis-border rounded-xl px-4 py-2.5 text-jarvis-text placeholder:text-jarvis-muted text-sm focus:outline-none focus:ring-1 focus:ring-jarvis-accent-primary"
            />
            <input
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Notes / tags (optional)"
              className="bg-jarvis-panel border border-jarvis-border rounded-xl px-4 py-2.5 text-jarvis-text placeholder:text-jarvis-muted text-sm focus:outline-none focus:ring-1 focus:ring-jarvis-accent-primary md:col-span-2"
            />
          </div>
          <button
            onClick={handleCreate}
            disabled={!name.trim()}
            className="mt-4 px-6 py-2.5 rounded-[4px] bg-jarvis-accent-primary text-white text-sm font-medium hover:bg-jarvis-accent-hover disabled:opacity-40 transition-all"
          >
            Save Contact
          </button>
        </div>
      )}

      {/* Contact List */}
      <div className="flex-1 overflow-y-auto z-10 pb-8">
        {loading ? (
          <div className="flex items-center justify-center h-40">
            <div className="text-jarvis-muted text-sm">Loading...</div>
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-40 text-jarvis-muted">
            <UserCircleIcon className="w-12 h-12 mb-3 opacity-30" />
            <p className="text-sm">
              {searchQuery ? "No contacts match your search" : "No contacts yet. Add one above."}
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {filtered.map((contact) => (
              <div
                key={contact.id}
                className="p-5 rounded-[8px] bg-jarvis-surface border border-transparent hover:border-jarvis-border shadow-[0_2px_8px_rgba(0,0,0,0.04)] hover:shadow-[0_4px_16px_rgba(0,0,0,0.1)] transition-all duration-200 group"
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-jarvis-accent-primary/20 flex items-center justify-center">
                      <UserCircleIcon className="w-6 h-6 text-jarvis-accent-primary" />
                    </div>
                    <div>
                      <h4 className="text-[15px] font-medium text-jarvis-text">
                        {contact.name}
                      </h4>
                      {contact.relationship && (
                        <span className="text-[11px] text-jarvis-muted capitalize">
                          {contact.relationship}
                        </span>
                      )}
                    </div>
                  </div>
                  <button
                    onClick={() => handleDelete(contact.id)}
                    className="text-jarvis-muted/30 hover:text-red-400 transition-colors opacity-0 group-hover:opacity-100"
                  >
                    <TrashIcon className="w-4 h-4" />
                  </button>
                </div>

                <div className="mt-3 space-y-1.5">
                  {contact.email && (
                    <div className="flex items-center gap-2 text-[13px] text-jarvis-muted">
                      <EnvelopeIcon className="w-4 h-4 text-jarvis-accent-cyan" />
                      {contact.email}
                    </div>
                  )}
                  {contact.phone && (
                    <div className="flex items-center gap-2 text-[13px] text-jarvis-muted">
                      <PhoneIcon className="w-4 h-4 text-jarvis-accent-cyan" />
                      {contact.phone}
                    </div>
                  )}
                  {contact.notes && (
                    <p className="text-[12px] text-jarvis-muted/60 mt-2 italic">
                      {contact.notes}
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
