import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../providers/upload_provider.dart';
import '../../services/image_picker_service.dart';

class UploadSourceSheet extends ConsumerStatefulWidget {
  const UploadSourceSheet({super.key});

  @override
  ConsumerState<UploadSourceSheet> createState() =>
      _UploadSourceSheetState();
}

class _UploadSourceSheetState
    extends ConsumerState<UploadSourceSheet> {
  bool _isPicking = false;

  Future<void> _takePhoto() async {
    if (_isPicking) {
      return;
    }

    setState(() {
      _isPicking = true;
    });

    try {
      final image =
          await ImagePickerService.instance.pickFromCamera();

      if (image == null || !mounted) {
        return;
      }

      ref.read(uploadProvider.notifier).addImage(image);

      Navigator.of(context).pop();
    } catch (error) {
      if (!mounted) {
        return;
      }

      _showError(
        'The camera image could not be added: $error',
      );
    } finally {
      if (mounted) {
        setState(() {
          _isPicking = false;
        });
      }
    }
  }

  Future<void> _chooseSingleImage() async {
    if (_isPicking) {
      return;
    }

    setState(() {
      _isPicking = true;
    });

    try {
      final image = await ImagePickerService.instance
          .pickSingleFromGallery();

      if (image == null || !mounted) {
        return;
      }

      ref.read(uploadProvider.notifier).addImage(image);

      Navigator.of(context).pop();
    } catch (error) {
      if (!mounted) {
        return;
      }

      _showError(
        'The selected image could not be added: $error',
      );
    } finally {
      if (mounted) {
        setState(() {
          _isPicking = false;
        });
      }
    }
  }

  Future<void> _chooseMultipleImages() async {
    if (_isPicking) {
      return;
    }

    setState(() {
      _isPicking = true;
    });

    try {
      final images = await ImagePickerService.instance
          .pickMultipleFromGallery();

      if (images.isEmpty || !mounted) {
        return;
      }

      ref.read(uploadProvider.notifier).addImages(images);

      Navigator.of(context).pop();
    } catch (error) {
      if (!mounted) {
        return;
      }

      _showError(
        'The selected images could not be added: $error',
      );
    } finally {
      if (mounted) {
        setState(() {
          _isPicking = false;
        });
      }
    }
  }

  void _showError(String message) {
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(
        SnackBar(
          content: Text(message),
        ),
      );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final uploadState = ref.watch(uploadProvider);

    final disabled =
        _isPicking || uploadState.isUploading;

    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(
          20,
          4,
          20,
          24,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Add meal images',
              style: theme.textTheme.headlineSmall?.copyWith(
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Take a new photo or choose one or more images from your gallery.',
              style: theme.textTheme.bodyLarge?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 22),

            _SourceOption(
              icon: Icons.camera_alt_rounded,
              title: 'Take a photo',
              description:
                  'Capture the meal using your rear camera.',
              enabled: !disabled,
              onTap: _takePhoto,
            ),
            const SizedBox(height: 12),

            _SourceOption(
              icon: Icons.photo_outlined,
              title: 'Choose one image',
              description:
                  'Select a single meal photo from your gallery.',
              enabled: !disabled,
              onTap: _chooseSingleImage,
            ),
            const SizedBox(height: 12),

            _SourceOption(
              icon: Icons.photo_library_outlined,
              title: 'Choose multiple images',
              description:
                  'Select multiple dishes or different meal angles.',
              enabled: !disabled,
              onTap: _chooseMultipleImages,
            ),

            if (_isPicking) ...[
              const SizedBox(height: 22),
              const LinearProgressIndicator(),
              const SizedBox(height: 10),
              Text(
                'Opening image picker…',
                style: theme.textTheme.bodyMedium?.copyWith(
                  color:
                      theme.colorScheme.onSurfaceVariant,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _SourceOption extends StatelessWidget {
  final IconData icon;
  final String title;
  final String description;
  final bool enabled;
  final VoidCallback onTap;

  const _SourceOption({
    required this.icon,
    required this.title,
    required this.description,
    required this.enabled,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Material(
      color: enabled
          ? theme.colorScheme.surfaceContainerLow
          : theme.colorScheme.surfaceContainerLow
              .withOpacity(0.55),
      borderRadius: BorderRadius.circular(20),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: enabled ? onTap : null,
        child: Container(
          width: double.infinity,
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(20),
            border: Border.all(
              color: theme.colorScheme.outlineVariant,
            ),
          ),
          child: Row(
            children: [
              Container(
                width: 50,
                height: 50,
                decoration: BoxDecoration(
                  color: theme.colorScheme.primaryContainer,
                  shape: BoxShape.circle,
                ),
                alignment: Alignment.center,
                child: Icon(
                  icon,
                  color:
                      theme.colorScheme.onPrimaryContainer,
                ),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment:
                      CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style:
                          theme.textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      description,
                      style:
                          theme.textTheme.bodyMedium?.copyWith(
                        color: theme
                            .colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 10),
              Icon(
                Icons.chevron_right_rounded,
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
