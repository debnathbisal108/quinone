```dart
import 'package:image_picker/image_picker.dart';

import '../models/upload_image.dart';

class ImagePickerService {
  ImagePickerService._();

  static final ImagePickerService instance =
      ImagePickerService._();

  final ImagePicker _picker = ImagePicker();

  // -------------------------------------------------------
  // Camera
  // -------------------------------------------------------

  Future<UploadImage?> pickFromCamera() async {
    final pickedFile = await _picker.pickImage(
      source: ImageSource.camera,
      imageQuality: 88,
      preferredCameraDevice: CameraDevice.rear,
    );

    if (pickedFile == null) {
      return null;
    }

    return UploadImage(
      id: _createId(pickedFile.path),
      path: pickedFile.path,
      type: UploadImageType.meal,
      status: UploadStatus.ready,
    );
  }

  // -------------------------------------------------------
  // Single gallery image
  // -------------------------------------------------------

  Future<UploadImage?>
      pickSingleFromGallery() async {
    final pickedFile = await _picker.pickImage(
      source: ImageSource.gallery,
      imageQuality: 88,
    );

    if (pickedFile == null) {
      return null;
    }

    return UploadImage(
      id: _createId(pickedFile.path),
      path: pickedFile.path,
      type: UploadImageType.meal,
      status: UploadStatus.ready,
    );
  }

  // -------------------------------------------------------
  // Multiple gallery images
  // -------------------------------------------------------

  Future<List<UploadImage>>
      pickMultipleFromGallery() async {
    final pickedFiles = await _picker.pickMultiImage(
      imageQuality: 88,
    );

    if (pickedFiles.isEmpty) {
      return const [];
    }

    return pickedFiles
        .map(
          (file) => UploadImage(
            id: _createId(file.path),
            path: file.path,
            type: UploadImageType.meal,
            status: UploadStatus.ready,
          ),
        )
        .toList();
  }

  // -------------------------------------------------------
  // Nutrition-label camera image
  // -------------------------------------------------------

  Future<UploadImage?>
      pickBackLabelFromCamera() async {
    final pickedFile = await _picker.pickImage(
      source: ImageSource.camera,
      imageQuality: 95,
      preferredCameraDevice: CameraDevice.rear,
    );

    if (pickedFile == null) {
      return null;
    }

    return UploadImage(
      id: _createId(pickedFile.path),
      path: pickedFile.path,
      type: UploadImageType.backLabel,
      status: UploadStatus.ready,
    );
  }

  // -------------------------------------------------------
  // Nutrition-label gallery image
  // -------------------------------------------------------

  Future<UploadImage?>
      pickBackLabelFromGallery() async {
    final pickedFile = await _picker.pickImage(
      source: ImageSource.gallery,
      imageQuality: 95,
    );

    if (pickedFile == null) {
      return null;
    }

    return UploadImage(
      id: _createId(pickedFile.path),
      path: pickedFile.path,
      type: UploadImageType.backLabel,
      status: UploadStatus.ready,
    );
  }

  String _createId(String path) {
    return '${DateTime.now().microsecondsSinceEpoch}_${path.hashCode}';
  }
}
```
