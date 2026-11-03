ALTER TABLE moara.chats ADD COLUMN assistant_id varchar(32) NOT NULL DEFAULT 'auto';
ALTER TABLE moara.chats ADD COLUMN document_ids jsonb NOT NULL DEFAULT '[]';
ALTER TABLE moara.chats ADD CONSTRAINT moara_chat_document_list CHECK(jsonb_typeof(document_ids)='array' AND jsonb_array_length(document_ids)<=16);
