import 'package:image_picker/image_picker.dart';

import '../models/upload_image.dart';

class ImagePickerService {
  ImagePickerService._();

  static final ImagePickerService instance = ImagePickerService._();

  final ImagePicker _picker = ImagePicker();

  Future<UploadImage?> pickFromCamera() async {
    final XFile? pickedFile = await _picker.pickImage(
      source: ImageSource.camera,
      imageQuality: 88,
      preferredCameraDevice: CameraDevice.rear,
    );

    return _toUploadImage(
      pickedFile,
      type: UploadImageType.meal,
    );
  }

  Future<UploadImage?> pickSingleFromGallery() async {
    final XFile? pickedFile = await _picker.pickImage(
      source: ImageSource.gallery,
      imageQuality: 88,
    );

    return _toUploadImage(
      pickedFile,
      type: UploadImageType.meal,
    );
  }

  Future<List<UploadImage>> pickMultipleFromGallery() async {
    final List<XFile> pickedFiles = await _picker.pickMultiImage(
      imageQuality: 88,
    );

    return pickedFiles
        .map(
          (file) => UploadImage(
            id: _createId(file.path),
            path: file.path,
            type: UploadImageType.meal,
            status: UploadStatus.ready,
          ),
        )
        .toList(growable: false);
  }

  Future<UploadImage?> pickBackLabelFromCamera() async {
    final XFile? pickedFile = await _picker.pickImage(
      source: ImageSource.camera,
      imageQuality: 95,
      preferredCameraDevice: CameraDevice.rear,
    );

    return _toUploadImage(
      pickedFile,
      type: UploadImageType.backLabel,
    );
  }

  Future<UploadImage?> pickBackLabelFromGallery() async {
    final XFile? pickedFile = await _picker.pickImage(
      source: ImageSource.gallery,
      imageQuality: 95,
    );

    return _toUploadImage(
      pickedFile,
      type: UploadImageType.backLabel,
    );
  }

  UploadImage? _toUploadImage(
    XFile? file, {
    required UploadImageType type,
  }) {
    if (file == null) {
      return null;
    }

    return UploadImage(
      id: _createId(file.path),
      path: file.path,
      type: type,
      status: UploadStatus.ready,
    );
  }

  String _createId(String path) {
    return '${DateTime.now().microsecondsSinceEpoch}_${path.hashCode}';
  }
}
