"use client";

import { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Upload, FileText, Trash2, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { ChatLayout } from "@/components/chat/chat-layout";
import { Button } from "@/components/ui/button";
import { cn, formatNumber } from "@/lib/utils";

interface UserFile {
  id: string;
  name: string;
  file_type: string;
  file_size: number;
  indexing_status: string;
  chunk_count: number;
  created_at: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function FilesPage() {
  const router = useRouter();
  const { getToken, isLoaded, isSignedIn } = useAuth();
  const [token, setToken] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!isSignedIn) return;
    let active = true;
    getToken().then((t) => {
      if (active && t) setToken(t);
    });
    return () => {
      active = false;
    };
  }, [isSignedIn, getToken]);

  useEffect(() => {
    if (isLoaded && !isSignedIn) {
      router.push("/sign-in");
    }
  }, [isLoaded, isSignedIn, router]);

  const { data: files, isLoading } = useQuery({
    queryKey: ["files", token],
    queryFn: async () => {
      const res = await fetch(`${API_URL}/api/v1/files/documents`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Failed to fetch files");
      return res.json();
    },
    enabled: !!token,
  });

  const uploadMutation = useMutation({
    mutationFn: async (file: File) => {
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch(`${API_URL}/api/v1/files/upload`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });
      if (!res.ok) {
        const error = await res.json().catch(() => ({}));
        throw new Error(error.detail || "Upload failed");
      }
      return res.json();
    },
    onSuccess: (data: UserFile) => {
      toast.success(`تم رفع "${data.name}" بنجاح (${data.chunk_count} قطعة)`);
      queryClient.invalidateQueries({ queryKey: ["files"] });
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const deleteMutation = useMutation({
    mutationFn: async (fileId: string) => {
      const res = await fetch(`${API_URL}/api/v1/files/documents/${fileId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Delete failed");
    },
    onMutate: async (fileId: string) => {
      await queryClient.cancelQueries({ queryKey: ["files"] });
      const previousFiles = queryClient.getQueryData(["files"]);
      queryClient.setQueryData(["files"], (old: UserFile[]) =>
        old?.filter((f) => f.id !== fileId)
      );
      return { previousFiles };
    },
    onError: (err, fileId, context) => {
      queryClient.setQueryData(["files"], context?.previousFiles);
      toast.error("Failed to delete file");
    },
    onSuccess: () => {
      toast.success("تم حذف الملف");
      queryClient.invalidateQueries({ queryKey: ["files"] });
    },
  });

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(e.target.files || []);
    if (!selectedFiles.length) return;
    setUploading(true);
    for (const file of selectedFiles) {
      setUploadProgress(`جارٍ رفع: ${file.name}`);
      await uploadMutation.mutateAsync(file);
    }
    setUploading(false);
    setUploadProgress("");
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const droppedFiles = Array.from(e.dataTransfer.files);
    if (!droppedFiles.length) return;
    setUploading(true);
    (async () => {
      for (const file of droppedFiles) {
        setUploadProgress(`جارٍ رفع: ${file.name}`);
        await uploadMutation.mutateAsync(file);
      }
      setUploading(false);
      setUploadProgress("");
    })();
  };

  if (!isLoaded || !isSignedIn) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <ChatLayout>
      <div className="flex-1 overflow-y-auto">
        <header className="border-b p-4">
          <h1 className="text-2xl font-bold">ملفاتي</h1>
          <p className="text-sm text-muted-foreground mt-1">
            ارفع ملفاتك وسيقوم NorX بالبحث فيها عند الحاجة
          </p>
        </header>

        <div className="p-4 max-w-4xl mx-auto">
          <div
            onClick={() => fileInputRef.current?.click()}
            onDrop={handleDrop}
            onDragOver={(e) => e.preventDefault()}
            className="border-2 border-dashed border-border rounded-2xl p-8 text-center hover:border-primary/50 hover:bg-secondary/30 cursor-pointer transition-colors mb-6"
          >
            <input
              ref={fileInputRef}
              type="file"
              multiple
              onChange={handleFileSelect}
              accept=".pdf,.docx,.doc,.txt,.md,.csv,.json,.html,.htm,.xlsx,.pptx"
              className="hidden"
            />
            <div className="w-14 h-14 rounded-2xl bg-primary/10 flex items-center justify-center mx-auto mb-3">
              <Upload className="w-7 h-7 text-primary" />
            </div>
            <p className="font-medium mb-1">اسحب الملفات هنا أو اضغط للاختيار</p>
            <p className="text-xs text-muted-foreground">
              PDF, DOCX, TXT, MD, CSV, JSON, HTML, XLSX, PPTX (حد أقصى 10MB)
            </p>
          </div>

          {uploading && (
            <div className="mb-4 p-3 bg-primary/10 rounded-lg flex items-center gap-2 text-sm">
              <Loader2 className="w-4 h-4 animate-spin text-primary" />
              <span>{uploadProgress}</span>
            </div>
          )}

          {isLoading ? (
            <div className="text-center py-8">
              <Loader2 className="w-6 h-6 animate-spin mx-auto text-muted-foreground" />
            </div>
          ) : files?.length ? (
            <div className="space-y-2">
              <div className="text-sm font-medium text-muted-foreground mb-2">
                الملفات المرفوعة ({files.length})
              </div>
              {files.map((file) => (
                <FileItem
                  key={file.id}
                  file={file}
                  onDelete={() => deleteMutation.mutate(file.id)}
                  isDeleting={deleteMutation.isPending}
                />
              ))}
            </div>
          ) : (
            <div className="text-center py-12 text-muted-foreground">
              <FileText className="w-12 h-12 mx-auto mb-3 opacity-30" />
              <p>لا توجد ملفات مرفوعة بعد</p>
              <p className="text-xs mt-1">ارفع ملفك الأول ليتمكن NorX من البحث فيه</p>
            </div>
          )}
        </div>
      </div>
    </ChatLayout>
  );
}

function FileItem({
  file,
  onDelete,
  isDeleting,
}: {
  file: UserFile;
  onDelete: () => void;
  isDeleting: boolean;
}) {
  const fileIcon = getFileIcon(file.file_type);
  const statusColors: Record<string, string> = {
    indexed: "text-green-600 bg-green-500/10",
    indexing: "text-blue-600 bg-blue-500/10",
    pending: "text-yellow-600 bg-yellow-500/10",
    failed: "text-red-600 bg-red-500/10",
  };
  const statusLabels: Record<string, string> = {
    indexed: "✓ مفهرس",
    indexing: "جارٍ الفهرسة",
    pending: "في الانتظار",
    failed: "✗ فشل",
  };

  return (
    <div className="flex items-center gap-3 p-3 rounded-xl border border-border bg-card hover:shadow-sm transition-shadow">
      <div className="w-10 h-10 rounded-lg bg-secondary flex items-center justify-center shrink-0 text-lg">
        {fileIcon}
      </div>
      <div className="flex-1 min-w-0">
        <div className="font-medium truncate">{file.name}</div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground mt-0.5">
          <span>{formatNumber(file.file_size)} بايت</span>
          <span>•</span>
          <span>{file.chunk_count} قطعة</span>
          <span>•</span>
          <span className={cn("px-1.5 py-0.5 rounded text-[10px]", statusColors[file.indexing_status])}>
            {statusLabels[file.indexing_status] || file.indexing_status}
          </span>
        </div>
      </div>
      <Button
        variant="ghost"
        size="icon"
        onClick={onDelete}
        disabled={isDeleting}
        className="text-muted-foreground hover:text-destructive shrink-0"
      >
        <Trash2 className="w-4 h-4" />
      </Button>
    </div>
  );
}

function getFileIcon(fileType: string): string {
  const icons: Record<string, string> = {
    pdf: "📄",
    docx: "📝",
    doc: "📝",
    txt: "📃",
    md: "📝",
    csv: "📊",
    json: "🔧",
    html: "🌐",
    xlsx: "📈",
    pptx: "📊",
  };
  return icons[fileType] || "📄";
}
