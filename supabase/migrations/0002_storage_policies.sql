-- Storage RLS: dadhero/storage.py uploads generated page images under
-- {family_id}/{filename} in the "dadhero-pages" bucket. A private bucket
-- has NO access policies by default -- even the uploading user's own
-- request gets rejected with "new row violates row-level security
-- policy" until this exists. Confirmed by a real 403 during testing, not
-- assumed.

create policy "own files only" on storage.objects for all
  using (bucket_id = 'dadhero-pages' and (storage.foldername(name))[1] = auth.uid()::text)
  with check (bucket_id = 'dadhero-pages' and (storage.foldername(name))[1] = auth.uid()::text);
