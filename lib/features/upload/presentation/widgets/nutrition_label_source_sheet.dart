import 'package:flutter/material.dart';

import '../../services/image_picker_service.dart';

class NutritionLabelSourceSheet extends StatelessWidget {
  const NutritionLabelSourceSheet({super.key, required this.onSelected});
  final ValueChanged<String> onSelected;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Nutrition label', style: theme.textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w900)),
            const SizedBox(height: 4),
            Text('Use a clear photo of the Nutrition Facts panel.', style: theme.textTheme.bodyMedium?.copyWith(color: theme.colorScheme.onSurfaceVariant)),
            const SizedBox(height: 16),
            Row(children: [
              Expanded(child: _SourceTile(icon: Icons.photo_camera_rounded, label: 'Camera', onTap: () async {
                final image = await ImagePickerService.instance.pickBackLabelFromCamera();
                if (image == null || !context.mounted) return;
                Navigator.pop(context); onSelected(image.path);
              })),
              const SizedBox(width: 12),
              Expanded(child: _SourceTile(icon: Icons.photo_library_rounded, label: 'Gallery', onTap: () async {
                final image = await ImagePickerService.instance.pickBackLabelFromGallery();
                if (image == null || !context.mounted) return;
                Navigator.pop(context); onSelected(image.path);
              })),
            ]),
          ],
        ),
      ),
    );
  }
}

class _SourceTile extends StatelessWidget {
  const _SourceTile({required this.icon, required this.label, required this.onTap});
  final IconData icon;
  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Material(
      color: scheme.surfaceContainerLow,
      borderRadius: BorderRadius.circular(20),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(20),
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 18),
          child: Column(children: [
            Icon(icon, size: 28, color: scheme.primary),
            const SizedBox(height: 8),
            Text(label, style: const TextStyle(fontWeight: FontWeight.w800)),
          ]),
        ),
      ),
    );
  }
}
